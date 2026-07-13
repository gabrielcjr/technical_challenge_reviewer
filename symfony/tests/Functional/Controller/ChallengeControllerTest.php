<?php

namespace App\Tests\Functional\Controller;

use Symfony\Bundle\FrameworkBundle\Test\WebTestCase;

class ChallengeControllerTest extends WebTestCase
{
    public function testChallengeNewFormLoads(): void
    {
        $client = static::createClient();
        $client->request('GET', '/challenges/new');

        $this->assertResponseIsSuccessful();
        $this->assertSelectorExists('form');
    }

    public function testApiListChallenges(): void
    {
        $client = static::createClient();
        $client->request('GET', '/api/challenges');

        $this->assertResponseIsSuccessful();
        $this->assertTrue(str_contains($client->getResponse()->headers->get('Content-Type'), 'application/json'));
    }

    public function testApiCreateChallenge(): void
    {
        $client = static::createClient();
        $client->request('POST', '/api/challenges', [], [], [
            'CONTENT_TYPE' => 'application/json'
        ], json_encode([
            'title' => 'Functional Test Challenge',
            'description' => 'This is a functional test challenge description that is long enough.'
        ]));

        $this->assertResponseStatusCodeSame(201);
        $data = json_decode($client->getResponse()->getContent(), true);
        $this->assertArrayHasKey('id', $data);
        $this->assertEquals('Functional Test Challenge', $data['title']);
    }

    public function testApiCreateChallengeValidationFails(): void
    {
        $client = static::createClient();
        $client->request('POST', '/api/challenges', [], [], [
            'CONTENT_TYPE' => 'application/json'
        ], json_encode([
            'title' => '',
            'description' => 'short'
        ]));

        $this->assertResponseStatusCodeSame(400);
    }
}
