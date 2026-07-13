<?php

namespace App\Message;

final class EvaluateSubmissionMessage
{
    public function __construct(
        public readonly string $submissionId,
    ) {
    }
}
