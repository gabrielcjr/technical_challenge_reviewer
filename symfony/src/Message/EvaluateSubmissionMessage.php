<?php

namespace App\Message;

use Symfony\Component\Uid\Uuid;
use Symfony\Component\Validator\Constraints as Assert;

final class EvaluateSubmissionMessage
{
    public readonly string $submissionId;

    public function __construct(string $submissionId)
    {
        if (!Uuid::isValid($submissionId)) {
            throw new \InvalidArgumentException(sprintf('Invalid UUID: %s', $submissionId));
        }
        $this->submissionId = $submissionId;
    }

    public function getSubmissionUuid(): Uuid
    {
        return Uuid::fromString($this->submissionId);
    }
}
