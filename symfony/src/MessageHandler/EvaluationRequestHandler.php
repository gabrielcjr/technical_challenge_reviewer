<?php

namespace App\MessageHandler;

use App\Entity\Submission;
use App\Enum\SubmissionStatus;
use App\Message\EvaluateSubmissionMessage;
use App\Repository\SubmissionRepository;
use App\Service\EvaluationWebhookService;
use Doctrine\ORM\EntityManagerInterface;
use Psr\Log\LoggerInterface;
use Symfony\Component\Messenger\Attribute\AsMessageHandler;
use Symfony\Component\Uid\Uuid;

#[AsMessageHandler]
class EvaluationRequestHandler
{
    public function __construct(
        private readonly SubmissionRepository $submissionRepository,
        private readonly EvaluationWebhookService $webhookService,
        private readonly EntityManagerInterface $em,
        private readonly LoggerInterface $logger,
    ) {
    }

    public function __invoke(EvaluateSubmissionMessage $message): void
    {
        $this->logger->info('Handling EvaluateSubmissionMessage', ['submissionId' => $message->submissionId]);

        $uuid = Uuid::fromString($message->submissionId);
        $submission = $this->submissionRepository->find($uuid);

        if (!$submission) {
            $this->logger->error('Submission not found', ['id' => $message->submissionId]);
            return;
        }

        // Update status to PROCESSING
        $submission->setStatus(SubmissionStatus::PROCESSING);
        $submission->setProcessingLogs('Dispatching to evaluator at ' . (new \DateTimeImmutable())->format('c'));
        $this->em->flush();

        try {
            $this->webhookService->dispatch($submission);
            $this->logger->info('Evaluation dispatched successfully', ['id' => $message->submissionId]);
        } catch (\Throwable $e) {
            $this->logger->error('Failed to dispatch evaluation', [
                'id' => $message->submissionId,
                'error' => $e->getMessage(),
            ]);

            // Keep as PROCESSING? Or set to PENDING for retry? Let's set back to PENDING with log and rethrow to trigger Messenger retry
            $submission->setProcessingLogs(
                ($submission->getProcessingLogs() ?? '') . "\n" . 'Dispatch failed: ' . $e->getMessage()
            );
            $this->em->flush();

            // Rethrow to let Messenger handle retry via retry_strategy
            throw $e;
        }
    }
}
