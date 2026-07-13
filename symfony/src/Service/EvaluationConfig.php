<?php

namespace App\Service;

final class EvaluationConfig
{
    public const EVALUATE_PATH = '/evaluate';

    public function __construct(
        public readonly string $evaluatorUrl,
        public readonly string $callbackUrl,
        public readonly string $callbackToken,
    ) {
    }

    public function getEvaluatorEndpoint(): string
    {
        return rtrim($this->evaluatorUrl, '/') . self::EVALUATE_PATH;
    }
}
