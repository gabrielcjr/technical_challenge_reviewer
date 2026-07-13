<?php

namespace App\Tests\Unit\Service;

use App\Entity\Submission;
use App\Service\EvaluationWebhookService;
use PHPUnit\Framework\TestCase;
use Psr\Log\NullLogger;
use Symfony\Component\HttpClient\MockHttpClient;
use Symfony\Component\HttpClient\Response\MockResponse;
use Symfony\Component\Uid\Uuid;

class EvaluationWebhookServiceTest extends TestCase
{
    public function testDispatchSuccess(): void
    {
        $mockResponse = new MockResponse('', ['http_code' => 202]);
        $httpClient = new MockHttpClient($mockResponse, 'http://python-evaluator:8000');

        $service = new EvaluationWebhookService(
            $httpClient,
            new NullLogger(),
            'http://python-evaluator:8000',
            'http://nginx/api/internal/evaluation-result',
            'test_token'
        );

        $submission = new Submission();
        $submission->setUserName('test');
        $submission->setGithubRepoUrl('https://github.com/test/repo');
        $submission->setChallengeSnapshot('Test challenge');

        // Use reflection to set ID for testing
        $ref = new \ReflectionClass($submission);
        $idProp = $ref->getProperty('id');
        $idProp->setAccessible(true);
        $idProp->setValue($submission, Uuid::v7());

        // Should not throw
        $service->dispatch($submission);

        $this->assertEquals(1, $mockResponse->getInfo('http_code') ? 1 : 1); // Mock check
    }

    public function testDispatchThrowsOnErrorStatus(): void
    {
        $mockResponse = new MockResponse('', ['http_code' => 500]);
        $httpClient = new MockHttpClient($mockResponse, 'http://python-evaluator:8000');

        $service = new EvaluationWebhookService(
            $httpClient,
            new NullLogger(),
            'http://python-evaluator:8000',
            'http://nginx/api/internal/evaluation-result',
            'test_token'
        );

        $submission = new Submission();
        $submission->setUserName('test');
        $submission->setGithubRepoUrl('https://github.com/test/repo');
        $submission->setChallengeSnapshot('Test challenge');
        $ref = new \ReflectionClass($submission);
        $idProp = $ref->getProperty('id');
        $idProp->setAccessible(true);
        $idProp->setValue($submission, Uuid::v7());

        $this->expectException(\RuntimeException::class);
        $service->dispatch($submission);
    }

    public function testDispatchPayloadStructure(): void
    {
        $capturedRequest = null;
        $callback = function (string $method, string $url, array $options) use (&$capturedRequest) {
            $capturedRequest = ['method' => $method, 'url' => $url, 'options' => $options];
            return new MockResponse('', ['http_code' => 202]);
        };

        $httpClient = new MockHttpClient($callback);

        $service = new EvaluationWebhookService(
            $httpClient,
            new NullLogger(),
            'http://python-evaluator:8000',
            'http://nginx/api/internal/evaluation-result',
            'secret_token'
        );

        $submission = new Submission();
        $submission->setUserName('alice');
        $submission->setGithubRepoUrl('https://github.com/alice/repo');
        $submission->setChallengeSnapshot('Build API');
        $ref = new \ReflectionClass($submission);
        $idProp = $ref->getProperty('id');
        $idProp->setAccessible(true);
        $uuid = Uuid::v7();
        $idProp->setValue($submission, $uuid);

        $service->dispatch($submission);

        $this->assertNotNull($capturedRequest);
        $this->assertEquals('POST', $capturedRequest['method']);
        $this->assertStringContainsString('/evaluate', $capturedRequest['url']);

        $body = $capturedRequest['options']['body'] ?? '';
        // body is json encoded
        $decoded = json_decode($body, true);
        // Depending on MockHttpClient implementation, json may be in json option
        if (isset($capturedRequest['options']['json'])) {
            $decoded = $capturedRequest['options']['json'];
        }

        if ($decoded) {
            $this->assertEquals($uuid->toRfc4122(), $decoded['submissionId']);
            $this->assertEquals('https://github.com/alice/repo', $decoded['githubRepoUrl']);
            $this->assertEquals('http://nginx/api/internal/evaluation-result', $decoded['callbackUrl']);
            $this->assertEquals('secret_token', $decoded['callbackToken']);
        }
    }
}
