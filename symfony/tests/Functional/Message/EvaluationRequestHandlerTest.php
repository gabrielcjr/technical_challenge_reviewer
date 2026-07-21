<?php

namespace App\Tests\Functional\Message;

use App\Entity\Submission;
use App\Message\EvaluateSubmissionMessage;
use App\MessageHandler\EvaluationRequestHandler;
use Symfony\Bundle\FrameworkBundle\Test\KernelTestCase;
use Symfony\Component\HttpClient\MockHttpClient;
use Symfony\Component\HttpClient\Response\MockResponse;
use Psr\Log\NullLogger;
use App\Service\EvaluationWebhookService;
use App\Repository\SubmissionRepository;
use Doctrine\ORM\EntityManagerInterface;

class EvaluationRequestHandlerTest extends KernelTestCase
{
    public function testHandlerUpdatesStatusToProcessingOnSuccess(): void
    {
        self::bootKernel();

        $container = static::getContainer();
        $em = $container->get(EntityManagerInterface::class);
        $repo = $container->get(SubmissionRepository::class);

        // Create submission
        $submission = new Submission();
        $submission->setUserName('handler_test');
        $submission->setGithubRepoUrl('https://github.com/test/repo');
        $submission->setChallengeSnapshot('Test challenge long enough for validation.');

        $em->persist($submission);
        $em->flush();

        $id = $submission->getId()->toRfc4122();

        // Mock HTTP client that returns 202
        $mockResponse = new MockResponse('', ['http_code' => 202]);
        $httpClient = new MockHttpClient($mockResponse);

        $webhookService = new EvaluationWebhookService(
            $httpClient,
            new NullLogger(),
            'http://python-evaluator:8000',
            'http://nginx/api/internal/evaluation-result',
            'test_token'
        );

        $handler = new EvaluationRequestHandler(
            $repo,
            $webhookService,
            $em,
            new NullLogger()
        );

        $message = new EvaluateSubmissionMessage($id);

        // Should not throw
        $handler->__invoke($message);

        // Reload submission
        $em->clear();
        $updated = $repo->find($id);

        $this->assertNotNull($updated);
        $this->assertEquals('processing', $updated->getStatus()->value);

        // Cleanup
        $em->remove($updated);
        $em->flush();
    }

    public function testHandlerThrowsOnHttpFailure(): void
    {
        self::bootKernel();

        $container = static::getContainer();
        $em = $container->get(EntityManagerInterface::class);
        $repo = $container->get(SubmissionRepository::class);

        $submission = new Submission();
        $submission->setUserName('handler_fail_test');
        $submission->setGithubRepoUrl('https://github.com/test/repo');
        $submission->setChallengeSnapshot('Test challenge long enough for validation.');

        $em->persist($submission);
        $em->flush();

        $id = $submission->getId()->toRfc4122();

        // Mock HTTP client that returns 500
        $mockResponse = new MockResponse('', ['http_code' => 500]);
        $httpClient = new MockHttpClient($mockResponse);

        $webhookService = new EvaluationWebhookService(
            $httpClient,
            new NullLogger(),
            'http://python-evaluator:8000',
            'http://nginx/api/internal/evaluation-result',
            'test_token'
        );

        $handler = new EvaluationRequestHandler(
            $repo,
            $webhookService,
            $em,
            new NullLogger()
        );

        $message = new EvaluateSubmissionMessage($id);

        try {
            $handler->__invoke($message);
            $this->fail('Expected RuntimeException on HTTP failure');
        } catch (\RuntimeException) {
            // expected — messenger will retry; submission marked FAILED
        }

        $em->clear();
        $updated = $repo->find($id);
        $this->assertNotNull($updated);
        $this->assertEquals('failed', $updated->getStatus()->value);
        $this->assertTrue($updated->canBeRetried());

        // Cleanup
        $em->remove($updated);
        $em->flush();
    }

    public function testHandlerHandlesNonExistentSubmission(): void
    {
        self::bootKernel();

        $container = static::getContainer();
        $em = $container->get(EntityManagerInterface::class);
        $repo = $container->get(SubmissionRepository::class);

        $mockResponse = new MockResponse('', ['http_code' => 202]);
        $httpClient = new MockHttpClient($mockResponse);

        $webhookService = new EvaluationWebhookService(
            $httpClient,
            new NullLogger(),
            'http://python-evaluator:8000',
            'http://nginx/api/internal/evaluation-result',
            'test_token'
        );

        $handler = new EvaluationRequestHandler(
            $repo,
            $webhookService,
            $em,
            new NullLogger()
        );

        $message = new EvaluateSubmissionMessage('00000000-0000-0000-0000-000000000000');

        // Clean code: should throw Unrecoverable for missing entity
        $this->expectException(\Symfony\Component\Messenger\Exception\UnrecoverableMessageHandlingException::class);
        $handler->__invoke($message);
    }
}
