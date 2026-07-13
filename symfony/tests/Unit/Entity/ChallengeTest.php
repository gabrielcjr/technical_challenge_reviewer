<?php

namespace App\Tests\Unit\Entity;

use App\Entity\Challenge;
use PHPUnit\Framework\TestCase;

class ChallengeTest extends TestCase
{
    public function testCreateChallenge(): void
    {
        $challenge = new Challenge();
        $challenge->setTitle('Test Challenge');
        $challenge->setDescription('This is a test challenge description that is long enough to pass validation.');

        $this->assertNotNull($challenge->getId());
        $this->assertEquals('Test Challenge', $challenge->getTitle());
        $this->assertStringContainsString('test challenge', strtolower($challenge->getDescription()));
        $this->assertNotNull($challenge->getCreatedAt());
        $this->assertEquals('Test Challenge', (string) $challenge);
    }

    public function testSubmissionsCollection(): void
    {
        $challenge = new Challenge();
        $this->assertCount(0, $challenge->getSubmissions());
    }
}
