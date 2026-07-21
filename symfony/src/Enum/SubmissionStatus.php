<?php

namespace App\Enum;

enum SubmissionStatus: string
{
    case PENDING = 'pending';
    case PROCESSING = 'processing';
    case APPROVED = 'approved';
    case REJECTED = 'rejected';
    case FAILED = 'failed';

    public function label(): string
    {
        return match ($this) {
            self::PENDING => 'Pending',
            self::PROCESSING => 'Processing',
            self::APPROVED => 'Approved',
            self::REJECTED => 'Rejected',
            self::FAILED => 'Failed',
        };
    }

    public function isFinal(): bool
    {
        return match ($this) {
            self::APPROVED, self::REJECTED, self::FAILED => true,
            self::PENDING, self::PROCESSING => false,
        };
    }

    public function canBeRetried(): bool
    {
        // Non-final states and infrastructure failures can be re-queued.
        // APPROVED / REJECTED are terminal evaluation outcomes.
        return match ($this) {
            self::PENDING, self::PROCESSING, self::FAILED => true,
            self::APPROVED, self::REJECTED => false,
        };
    }
}
