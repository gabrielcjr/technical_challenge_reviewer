<?php

namespace App\Dto;

final class EvaluationCallbackPayload
{
    public function __construct(
        public readonly string $submissionId,
        public readonly bool $approved,
        public readonly string $summary,
        public readonly array $improvements,
        public readonly string $reasoning,
        public readonly ?string $rawOutput,
        public readonly bool $failed = false,
    ) {
    }

    public static function fromArray(array $data): self
    {
        $submissionId = $data['submissionId'] ?? '';
        $approved = $data['approved'] ?? null;
        $summary = $data['summary'] ?? '';
        $improvements = $data['improvements'] ?? [];
        $reasoning = $data['reasoning'] ?? $data['details'] ?? '';
        $rawOutput = $data['rawOutput'] ?? $data['raw'] ?? null;
        $failed = $data['failed'] ?? false;

        if ($submissionId === '') {
            throw new \InvalidArgumentException('submissionId required');
        }
        if ($approved === null && !$failed) {
            throw new \InvalidArgumentException('approved field required');
        }

        $approvedBool = false;
        if ($approved !== null) {
            $approvedBool = filter_var($approved, FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE);
            if ($approvedBool === null) {
                $approvedBool = (bool) $approved;
            }
        }

        $failedBool = filter_var($failed, FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE);
        if ($failedBool === null) {
            $failedBool = (bool) $failed;
        }

        // Infrastructure/process failures are never approvals.
        if ($failedBool) {
            $approvedBool = false;
        }

        if ($summary === '') {
            $summary = $failedBool
                ? 'Evaluation failed'
                : ($approvedBool ? 'Challenge approved' : 'Challenge not approved');
        }

        return new self(
            $submissionId,
            $approvedBool,
            (string) $summary,
            is_array($improvements) ? $improvements : [],
            (string) $reasoning,
            $rawOutput !== null ? (string) $rawOutput : null,
            $failedBool,
        );
    }
}
