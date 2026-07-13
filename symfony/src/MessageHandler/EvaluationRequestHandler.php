<?php

namespace App\MessageHandler;

use App\Entity\Submission;
use App\Message\EvaluateSubmissionMessage;
use App\Repository\SubmissionRepository;
use App\Service\EvaluationWebhookService;
use Doctrine\ORM\EntityManagerInterface;
use Psr\Clock\ClockInterface;
use Psr\Log\LoggerInterface;
use Symfony\Component\Clock\Clock;
use Symfony\Component\Messenger\Attribute\AsMessageHandler;
use Symfony\Component\Messenger\Exception\UnrecoverableMessageHandlingException;

#[AsMessageHandler]
class EvaluationRequestHandler
{
    private readonly ClockInterface $clock;

    public function __construct(
        private readonly SubmissionRepository $submissionRepository,
        private readonly EvaluationWebhookService $webhookService,
        private readonly EntityManagerInterface $entityManager,
        private readonly LoggerInterface $logger,
        ?ClockInterface $clock = null,
    ) {
        $this->clock = $clock ?? Clock::get();
    }

    public function __invoke(EvaluateSubmissionMessage $message): void
    {
        $this->logger->info('Handling evaluation message', ['submissionId' => $message->submissionId]);

        $submission = $this->findSubmissionOrFail($message);
        $this->markSubmissionAsProcessing($submission);
        $this->dispatchToEvaluator($submission, $message);
    }

    private function findSubmissionOrFail(EvaluateSubmissionMessage $message): Submission
    {
        $uuid = $message->getSubmissionUuid();
        $submission = $this->submissionRepository->find($uuid);

        if (!$submission) {
            $this->logger->error('Submission not found', ['id' => $message->submissionId]);
            throw new UnrecoverableMessageHandlingException(
                sprintf('Submission %s not found', $message->submissionId)
            );
        }

        return $submission;
    }

    private function markSubmissionAsProcessing(Submission $submission): void
    {
        $timestamp = $this->clock->now()->format(\DateTimeInterface::ATOM);
        $submission->markAsProcessing();
        $submission->appendProcessingLog(sprintf('Dispatching to evaluator at %s', $timestamp));
        $this->entityManager->flush();
    }

    private function dispatchToEvaluator(Submission $submission, EvaluateSubmissionMessage $message): void
    {
        try {
            $this->webhookService->dispatch($submission);
            $this->logger->info('Evaluation dispatched successfully', ['id' => $message->submissionId]);
        } catch (\Throwable $error) {
            $this->handleDispatchFailure($submission, $error);
            throw $error;
        }
    }

    private function handleDispatchFailure(Submission $submission, \Throwable $error): void
    {
        $this->logger->error('Failed to dispatch evaluation', [
            'id' => $submission->getIdAsString(),
            'error' => $error->getMessage(),
        ]);

        $submission->appendProcessingLog('Dispatch failed: ' . $error->getMessage());
        $this->entityManager->flush();
    }
}
