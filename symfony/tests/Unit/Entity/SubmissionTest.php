<?php

namespace App\Tests\Unit\Entity;

use App\Entity\Challenge;
use App\Entity\Submission;
use App\Enum\SubmissionStatus;
use PHPUnit\Framework\TestCase;

class SubmissionTest extends TestCase
{
    public function testCreateSubmission(): void
    {
        $submission = new Submission();
        $submission->setUserName('john_doe');
        $submission->setGithubRepoUrl('https://github.com/john/repo');
        $submission->setChallengeSnapshot('Build a TODO API');

        $this->assertNotNull($submission->getId());
        $this->assertEquals('john_doe', $submission->getUserName());
        $this->assertEquals('https://github.com/john/repo', $submission->getGithubRepoUrl());
        $this->assertEquals('Build a TODO API', $submission->getChallengeSnapshot());
        $this->assertEquals(SubmissionStatus::PENDING, $submission->getStatus());
        $this->assertNotNull($submission->getCreatedAt());
        $this->assertNotNull($submission->getUpdatedAt());
    }

    public function testSubmissionWithChallenge(): void
    {
        $challenge = new Challenge();
        $challenge->setTitle('TODO API');
        $challenge->setDescription('Build a TODO API with CRUD operations.');

        $submission = new Submission();
        $submission->setUserName('alice');
        $submission->setGithubRepoUrl('https://github.com/alice/todo');
        $submission->setChallenge($challenge);

        $this->assertEquals($challenge, $submission->getChallenge());
        $this->assertEquals($challenge->getDescription(), $submission->getChallengeSnapshot());
    }

    public function testStatusTransitions(): void
    {
        $submission = new Submission();
        $this->assertEquals(SubmissionStatus::PENDING, $submission->getStatus());

        $submission->setStatus(SubmissionStatus::PROCESSING);
        $this->assertEquals(SubmissionStatus::PROCESSING, $submission->getStatus());

        $submission->setStatus(SubmissionStatus::APPROVED);
        $submission->setApproved(true);
        $this->assertTrue($submission->isApproved());
        $this->assertTrue($submission->getStatus()->isFinal());

        $submission->setStatus(SubmissionStatus::REJECTED);
        $submission->setApproved(false);
        $this->assertFalse($submission->isApproved());
    }

    public function testEvaluationResult(): void
    {
        $submission = new Submission();
        $result = [
            'approved' => true,
            'summary' => 'Good job',
            'improvements' => ['Add tests'],
            'reasoning' => 'Meets requirements'
        ];
        $submission->setEvaluationResult($result);

        $this->assertEquals($result, $submission->getEvaluationResult());
        $this->assertEquals('Good job', $submission->getEvaluationResult()['summary']);
    }

    public function testToArray(): void
    {
        $submission = new Submission();
        $submission->setUserName('bob');
        $submission->setGithubRepoUrl('https://github.com/bob/repo');
        $submission->setChallengeSnapshot('Test challenge');

        $array = $submission->toArray();

        $this->assertArrayHasKey('id', $array);
        $this->assertArrayHasKey('userName', $array);
        $this->assertArrayHasKey('githubRepoUrl', $array);
        $this->assertArrayHasKey('status', $array);
        $this->assertEquals('bob', $array['userName']);
    }
}
