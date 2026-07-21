<?php

namespace App\Tests\Functional\Controller;

use App\Enum\SubmissionStatus;
use Symfony\Bundle\FrameworkBundle\Test\WebTestCase;

class InternalCallbackControllerTest extends WebTestCase
{
    public function testHealthEndpoint(): void
    {
        $client = static::createClient();
        $client->request('GET', '/api/internal/health');

        $this->assertResponseIsSuccessful();
        $data = json_decode($client->getResponse()->getContent(), true);
        $this->assertEquals('ok', $data['status']);
    }

    public function testCallbackRequiresValidToken(): void
    {
        $client = static::createClient();
        $client->request('POST', '/api/internal/evaluation-result', [], [], [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_X-INTERNAL-TOKEN' => 'invalid_token'
        ], json_encode([
            'submissionId' => '00000000-0000-0000-0000-000000000000',
            'approved' => true,
            'summary' => 'Good',
            'improvements' => []
        ]));

        $this->assertResponseStatusCodeSame(401);
    }

    public function testCallbackUpdatesSubmission(): void
    {
        $client = static::createClient();

        // Create a submission first
        $client->request('POST', '/api/submissions', [], [], [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_ACCEPT' => 'application/json'
        ], json_encode([
            'userName' => 'callback_test_user',
            'githubRepoUrl' => 'https://github.com/octocat/Hello-World',
            'customChallengeText' => 'Test challenge for callback test - long enough.'
        ]));

        $this->assertResponseStatusCodeSame(201);
        $submissionData = json_decode($client->getResponse()->getContent(), true);
        $submissionId = $submissionData['id'];

        // Now simulate Python callback with correct token
        // Get token from env or use configured one
        $token = $_ENV['CALLBACK_TOKEN'] ?? $_SERVER['CALLBACK_TOKEN'] ?? 's3cr3t_shared_token_change_me';

        $client->request('POST', '/api/internal/evaluation-result', [], [], [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_X-INTERNAL-TOKEN' => $token
        ], json_encode([
            'submissionId' => $submissionId,
            'approved' => true,
            'summary' => 'Excellent work! Meets all requirements.',
            'improvements' => ['Add more tests', 'Improve README'],
            'reasoning' => 'All endpoints implemented correctly.'
        ]));

        $this->assertResponseIsSuccessful();
        $responseData = json_decode($client->getResponse()->getContent(), true);
        $this->assertEquals('ok', $responseData['status']);
        $this->assertTrue($responseData['approved']);

        // Verify submission status updated
        $client->request('GET', "/api/submissions/{$submissionId}");
        $this->assertResponseIsSuccessful();
        $updated = json_decode($client->getResponse()->getContent(), true);
        $this->assertEquals('approved', $updated['status']);
        $this->assertTrue($updated['approved']);
        $this->assertEquals('Excellent work! Meets all requirements.', $updated['evaluation']['summary']);
    }

    public function testCallbackRejects(): void
    {
        $client = static::createClient();

        $client->request('POST', '/api/submissions', [], [], [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_ACCEPT' => 'application/json'
        ], json_encode([
            'userName' => 'reject_test',
            'githubRepoUrl' => 'https://github.com/octocat/Hello-World',
            'customChallengeText' => 'Challenge for reject test - long enough text.'
        ]));

        $this->assertResponseStatusCodeSame(201);
        $submissionId = json_decode($client->getResponse()->getContent(), true)['id'];

        $token = $_ENV['CALLBACK_TOKEN'] ?? $_SERVER['CALLBACK_TOKEN'] ?? 's3cr3t_shared_token_change_me';

        $client->request('POST', '/api/internal/evaluation-result', [], [], [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_X-INTERNAL-TOKEN' => $token
        ], json_encode([
            'submissionId' => $submissionId,
            'approved' => false,
            'summary' => 'Missing required endpoints',
            'improvements' => ['Implement GET /api/todos', 'Add validation'],
            'reasoning' => 'Core features missing'
        ]));

        $this->assertResponseIsSuccessful();

        $client->request('GET', "/api/submissions/{$submissionId}");
        $data = json_decode($client->getResponse()->getContent(), true);
        $this->assertEquals('rejected', $data['status']);
        $this->assertFalse($data['approved']);
    }

    public function testCallbackMissingFields(): void
    {
        $client = static::createClient();
        $token = $_ENV['CALLBACK_TOKEN'] ?? $_SERVER['CALLBACK_TOKEN'] ?? 's3cr3t_shared_token_change_me';

        $client->request('POST', '/api/internal/evaluation-result', [], [], [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_X-INTERNAL-TOKEN' => $token
        ], json_encode([
            'approved' => true
        ]));

        $this->assertResponseStatusCodeSame(400);
    }

    public function testCallbackFailedFlagMarksSubmissionFailed(): void
    {
        $client = static::createClient();

        $client->request('POST', '/api/submissions', [], [], [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_ACCEPT' => 'application/json'
        ], json_encode([
            'userName' => 'failed_callback_test',
            'githubRepoUrl' => 'https://github.com/octocat/Hello-World',
            'customChallengeText' => 'Challenge for failed callback test - long enough.'
        ]));

        $this->assertResponseStatusCodeSame(201);
        $submissionId = json_decode($client->getResponse()->getContent(), true)['id'];

        $token = $_ENV['CALLBACK_TOKEN'] ?? $_SERVER['CALLBACK_TOKEN'] ?? 's3cr3t_shared_token_change_me';

        $client->request('POST', '/api/internal/evaluation-result', [], [], [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_X-INTERNAL-TOKEN' => $token
        ], json_encode([
            'submissionId' => $submissionId,
            'approved' => false,
            'failed' => true,
            'summary' => 'Evaluation failed: clone error',
            'improvements' => ['Check repository URL is valid and public'],
            'reasoning' => 'git clone failed'
        ]));

        $this->assertResponseIsSuccessful();
        $responseData = json_decode($client->getResponse()->getContent(), true);
        $this->assertEquals('failed', $responseData['submissionStatus']);

        $client->request('GET', "/api/submissions/{$submissionId}");
        $data = json_decode($client->getResponse()->getContent(), true);
        $this->assertEquals('failed', $data['status']);
        $this->assertFalse($data['approved']);
        $this->assertEquals('Evaluation failed: clone error', $data['evaluation']['summary']);
    }
}
