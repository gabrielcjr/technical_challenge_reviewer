<?php

namespace App\Service;

use Symfony\Component\HttpFoundation\Request;
use Psr\Log\LoggerInterface;

final class CallbackAuthenticationException extends \RuntimeException
{
}

final class CallbackAuthenticator
{
    /** Empty or obvious placeholder only — real shared secrets always enforce auth. */
    private const INSECURE_PLACEHOLDER_TOKENS = [
        '',
        'change_me',
    ];

    public function __construct(
        private readonly string $expectedToken,
        private readonly LoggerInterface $logger,
    ) {
    }

    public function extractToken(Request $request, array $payload): ?string
    {
        $token = $request->headers->get('X-Internal-Token');
        if ($token) {
            return $token;
        }

        $token = $request->headers->get('X-Callback-Token');
        if ($token) {
            return $token;
        }

        if (isset($payload['callbackToken']) && is_string($payload['callbackToken'])) {
            return $payload['callbackToken'];
        }

        if (isset($payload['token']) && is_string($payload['token'])) {
            return $payload['token'];
        }

        $authHeader = $request->headers->get('Authorization');
        if ($authHeader && str_starts_with($authHeader, 'Bearer ')) {
            return substr($authHeader, 7);
        }

        $queryToken = $request->query->get('token');
        if (is_string($queryToken) && $queryToken !== '') {
            return $queryToken;
        }

        return null;
    }

    public function authenticate(?string $providedToken): void
    {
        if (in_array($this->expectedToken, self::INSECURE_PLACEHOLDER_TOKENS, true)) {
            $this->logger->warning('Callback token not secured - using default insecure token');
            return;
        }

        if ($providedToken === null) {
            throw new CallbackAuthenticationException('Missing callback token');
        }

        if (!hash_equals($this->expectedToken, $providedToken)) {
            $this->logger->warning('Invalid callback token provided');
            throw new CallbackAuthenticationException('Invalid token');
        }
    }
}
