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
        return in_array($this, [self::APPROVED, self::REJECTED, self::FAILED], true);
    }
}
