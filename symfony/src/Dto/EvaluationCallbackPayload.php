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

        if ($submissionId === '') {
            throw new \InvalidArgumentException('submissionId required');
        }
        if ($approved === null) {
            throw new \InvalidArgumentException('approved field required');
        }

        $approvedBool = filter_var($approved, FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE);
        if ($approvedBool === null) {
            $approvedBool = (bool) $approved;
        }

        if ($summary === '') {
            $summary = $approvedBool ? 'Challenge approved' : 'Challenge not approved';
        }

        return new self(
            $submissionId,
            $approvedBool,
            (string) $summary,
            is_array($improvements) ? $improvements : [],
            (string) $reasoning,
            $rawOutput !== null ? (string) $rawOutput : null,
        );
    }
}
