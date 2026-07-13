<?php

namespace App\Tests\Unit\Enum;

use App\Enum\SubmissionStatus;
use PHPUnit\Framework\TestCase;

class SubmissionStatusTest extends TestCase
{
    public function testLabel(): void
    {
        $this->assertEquals('Pending', SubmissionStatus::PENDING->label());
        $this->assertEquals('Approved', SubmissionStatus::APPROVED->label());
        $this->assertEquals('Rejected', SubmissionStatus::REJECTED->label());
        $this->assertEquals('Failed', SubmissionStatus::FAILED->label());
        $this->assertEquals('Processing', SubmissionStatus::PROCESSING->label());
    }

    public function testIsFinal(): void
    {
        $this->assertFalse(SubmissionStatus::PENDING->isFinal());
        $this->assertFalse(SubmissionStatus::PROCESSING->isFinal());
        $this->assertTrue(SubmissionStatus::APPROVED->isFinal());
        $this->assertTrue(SubmissionStatus::REJECTED->isFinal());
        $this->assertTrue(SubmissionStatus::FAILED->isFinal());
    }

    public function testEnumValues(): void
    {
        $this->assertEquals('pending', SubmissionStatus::PENDING->value);
        $this->assertEquals('approved', SubmissionStatus::APPROVED->value);
    }
}
