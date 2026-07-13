<?php

namespace App\Tests\Functional\Controller;

use App\Entity\Challenge;
use App\Enum\SubmissionStatus;
use Symfony\Bundle\FrameworkBundle\Test\WebTestCase;

class SubmissionControllerTest extends WebTestCase
{
    public function testHomePageLoads(): void
    {
        $client = static::createClient();
        $client->request('GET', '/');

        $this->assertResponseIsSuccessful();
        $this->assertSelectorTextContains('h1', 'Recent Submissions');
    }

    public function testNewSubmissionFormLoads(): void
    {
        $client = static::createClient();
        $client->request('GET', '/submissions/new');

        $this->assertResponseIsSuccessful();
        $this->assertSelectorExists('form#submissionForm');
    }

    public function testApiListSubmissions(): void
    {
        $client = static::createClient();
        $client->request('GET', '/api/submissions');

        $this->assertResponseIsSuccessful();
        $this->assertTrue(str_contains($client->getResponse()->headers->get('Content-Type'), 'application/json'));
    }

    public function testApiCreateSubmissionWithChallenge(): void
    {
        $client = static::createClient();

        // First create a challenge via API
        $client->request('POST', '/api/challenges', [], [], ['CONTENT_TYPE' => 'application/json'], json_encode([
            'title' => 'Test Challenge for Functional',
            'description' => 'Build a REST API with CRUD operations that is at least 20 chars long description for test.'
        ]));

        $this->assertResponseStatusCodeSame(201);
        $challengeData = json_decode($client->getResponse()->getContent(), true);
        $challengeId = $challengeData['id'];

        // Now create submission
        $client->request('POST', '/api/submissions', [], [], [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_ACCEPT' => 'application/json'
        ], json_encode([
            'userName' => 'functional_tester',
            'githubRepoUrl' => 'https://github.com/octocat/Hello-World',
            'challengeId' => $challengeId
        ]));

        $this->assertResponseStatusCodeSame(201);
        $data = json_decode($client->getResponse()->getContent(), true);
        $this->assertArrayHasKey('id', $data);
        $this->assertEquals('pending', $data['status']);

        // Check that submission exists via GET
        $submissionId = $data['id'];
        $client->request('GET', "/api/submissions/{$submissionId}");
        $this->assertResponseIsSuccessful();
        $getData = json_decode($client->getResponse()->getContent(), true);
        $this->assertEquals('functional_tester', $getData['userName']);
        $this->assertEquals('https://github.com/octocat/Hello-World', $getData['githubRepoUrl']);
    }

    public function testApiCreateSubmissionWithCustomText(): void
    {
        $client = static::createClient();
        $client->request('POST', '/api/submissions', [], [], [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_ACCEPT' => 'application/json'
        ], json_encode([
            'userName' => 'custom_challenge_user',
            'githubRepoUrl' => 'https://github.com/octocat/Hello-World',
            'customChallengeText' => 'Custom challenge: Build a simple API that does X, Y, Z. Must have tests and documentation.'
        ]));

        $this->assertResponseStatusCodeSame(201);
        $data = json_decode($client->getResponse()->getContent(), true);
        $this->assertArrayHasKey('id', $data);
    }

    public function testApiCreateSubmissionValidationFails(): void
    {
        $client = static::createClient();
        $client->request('POST', '/api/submissions', [], [], [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_ACCEPT' => 'application/json'
        ], json_encode([
            'userName' => '',
            'githubRepoUrl' => 'not-a-url',
            'customChallengeText' => 'short'
        ]));

        $this->assertResponseStatusCodeSame(400);
    }

    public function testApiCreateSubmissionInvalidGithubUrl(): void
    {
        $client = static::createClient();
        $client->request('POST', '/api/submissions', [], [], [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_ACCEPT' => 'application/json'
        ], json_encode([
            'userName' => 'test',
            'githubRepoUrl' => 'https://gitlab.com/user/repo',
            'customChallengeText' => 'This challenge text is long enough to pass validation for testing purposes.'
        ]));

        // Our controller checks for github.com presence
        $this->assertResponseStatusCodeSame(400);
    }

    public function testSubmissionShowPage(): void
    {
        $client = static::createClient();

        // Create submission first
        $client->request('POST', '/api/submissions', [], [], [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_ACCEPT' => 'application/json'
        ], json_encode([
            'userName' => 'show_page_user',
            'githubRepoUrl' => 'https://github.com/octocat/Hello-World',
            'customChallengeText' => 'Test challenge for show page - must be long enough.'
        ]));

        $this->assertResponseStatusCodeSame(201);
        $data = json_decode($client->getResponse()->getContent(), true);
        $id = $data['id'];

        $client->request('GET', "/submissions/{$id}");
        $this->assertResponseIsSuccessful();
    }

    public function testApiGetNonExistentSubmission(): void
    {
        $client = static::createClient();
        $client->request('GET', '/api/submissions/00000000-0000-0000-0000-000000000000');

        $this->assertResponseStatusCodeSame(404);
    }

    public function testApiRetryEndpoint(): void
    {
        $client = static::createClient();

        // Create submission
        $client->request('POST', '/api/submissions', [], [], [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_ACCEPT' => 'application/json'
        ], json_encode([
            'userName' => 'retry_user',
            'githubRepoUrl' => 'https://github.com/octocat/Hello-World',
            'customChallengeText' => 'Retry test challenge text long enough.'
        ]));

        $this->assertResponseStatusCodeSame(201);
        $data = json_decode($client->getResponse()->getContent(), true);
        $id = $data['id'];

        // Retry
        $client->request('POST', "/api/submissions/{$id}/retry");
        $this->assertResponseIsSuccessful();
        $retryData = json_decode($client->getResponse()->getContent(), true);
        $this->assertEquals('retry dispatched', $retryData['status']);
    }
}
