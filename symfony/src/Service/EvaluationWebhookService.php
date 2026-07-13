<?php

namespace App\Service;

use App\Entity\Submission;
use Psr\Log\LoggerInterface;
use Symfony\Contracts\HttpClient\HttpClientInterface;

class EvaluationWebhookService
{
    public function __construct(
        private readonly HttpClientInterface $httpClient,
        private readonly LoggerInterface $logger,
        private readonly string $evaluatorUrl,
        private readonly string $callbackUrl,
        private readonly string $callbackToken,
    ) {
    }

    /**
     * Sends submission data to Python evaluator via webhook.
     *
     * @throws \Symfony\Contracts\HttpClient\Exception\TransportExceptionInterface
     */
    public function dispatch(Submission $submission): void
    {
        $payload = [
            'submissionId' => $submission->getId()->toRfc4122(),
            'githubRepoUrl' => $submission->getGithubRepoUrl(),
            'challengeText' => $submission->getChallengeSnapshot(),
            'callbackUrl' => $this->callbackUrl,
            'callbackToken' => $this->callbackToken,
        ];

        $this->logger->info('Dispatching evaluation webhook', [
            'submissionId' => $payload['submissionId'],
            'evaluatorUrl' => $this->evaluatorUrl,
        ]);

        $response = $this->httpClient->request('POST', rtrim($this->evaluatorUrl, '/') . '/evaluate', [
            'json' => $payload,
            'timeout' => 10,
        ]);

        // Trigger request but don't necessarily wait long - we expect 202
        $statusCode = $response->getStatusCode();

        $this->logger->info('Evaluation webhook sent', [
            'submissionId' => $payload['submissionId'],
            'statusCode' => $statusCode,
        ]);

        if ($statusCode < 200 || $statusCode >= 300) {
            throw new \RuntimeException(sprintf('Evaluator responded with status %d', $statusCode));
        }
    }
}
