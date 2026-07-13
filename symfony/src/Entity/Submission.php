<?php

namespace App\Entity;

use App\Enum\SubmissionStatus;
use App\Repository\SubmissionRepository;
use Doctrine\DBAL\Types\Types;
use Doctrine\ORM\Mapping as ORM;
use Symfony\Component\Uid\Uuid;
use Symfony\Component\Validator\Constraints as Assert;

#[ORM\Entity(repositoryClass: SubmissionRepository::class)]
#[ORM\Table(name: 'submissions')]
#[ORM\HasLifecycleCallbacks]
class Submission
{
    private const MAX_LOG_LENGTH = 10000;

    #[ORM\Id]
    #[ORM\Column(type: 'uuid', unique: true)]
    private Uuid $id;

    #[ORM\Column(length: 180)]
    #[Assert\NotBlank]
    #[Assert\Length(min: 2, max: 180)]
    private string $userName = '';

    #[ORM\Column(length: 500)]
    #[Assert\NotBlank]
    #[Assert\Url(requireTld: true)]
    #[Assert\Length(max: 500)]
    private string $githubRepoUrl = '';

    #[ORM\ManyToOne(targetEntity: Challenge::class, inversedBy: 'submissions')]
    #[ORM\JoinColumn(nullable: true)]
    private ?Challenge $challenge = null;

    #[ORM\Column(type: Types::TEXT)]
    #[Assert\NotBlank]
    #[Assert\Length(min: 20)]
    private string $challengeSnapshot = '';

    #[ORM\Column(enumType: SubmissionStatus::class)]
    private SubmissionStatus $status;

    #[ORM\Column(type: Types::JSON, nullable: true)]
    private ?array $evaluationResult = null;

    #[ORM\Column(nullable: true)]
    private ?bool $approved = null;

    #[ORM\Column(type: Types::TEXT, nullable: true)]
    private ?string $processingLogs = null;

    #[ORM\Column]
    private \DateTimeImmutable $createdAt;

    #[ORM\Column]
    private \DateTimeImmutable $updatedAt;

    public function __construct()
    {
        $this->id = Uuid::v7();
        $this->status = SubmissionStatus::PENDING;
        $this->createdAt = new \DateTimeImmutable();
        $this->updatedAt = new \DateTimeImmutable();
    }

    #[ORM\PreUpdate]
    public function onPreUpdate(): void
    {
        $this->updatedAt = new \DateTimeImmutable();
    }

    // --- Core getters - non-nullable for invariants ---
    public function getId(): Uuid
    {
        return $this->id;
    }

    public function getIdAsString(): string
    {
        return $this->id->toRfc4122();
    }

    public function getUserName(): string
    {
        return $this->userName;
    }

    public function setUserName(string $userName): static
    {
        $this->userName = $userName;
        return $this;
    }

    public function getGithubRepoUrl(): string
    {
        return $this->githubRepoUrl;
    }

    public function setGithubRepoUrl(string $githubRepoUrl): static
    {
        $this->githubRepoUrl = $githubRepoUrl;
        return $this;
    }

    public function getChallenge(): ?Challenge
    {
        return $this->challenge;
    }

    /**
     * Associates submission with a challenge and snapshots description.
     * Explicit intention - replaces hidden side effect in setter.
     */
    public function associateWithChallenge(?Challenge $challenge): static
    {
        $this->challenge = $challenge;
        if ($challenge !== null) {
            $this->snapshotFromChallenge($challenge);
        }
        return $this;
    }

    /**
     * @deprecated Use associateWithChallenge - kept for backward compatibility
     */
    public function setChallenge(?Challenge $challenge): static
    {
        return $this->associateWithChallenge($challenge);
    }

    public function snapshotFromChallenge(Challenge $challenge): void
    {
        $this->challengeSnapshot = $challenge->getDescription();
    }

    public function getChallengeSnapshot(): string
    {
        return $this->challengeSnapshot;
    }

    public function setChallengeSnapshot(string $challengeSnapshot): static
    {
        $this->challengeSnapshot = $challengeSnapshot;
        return $this;
    }

    public function getStatus(): SubmissionStatus
    {
        return $this->status;
    }

    public function setStatus(SubmissionStatus $status): static
    {
        $this->status = $status;
        return $this;
    }

    public function getEvaluationResult(): ?array
    {
        return $this->evaluationResult;
    }

    public function setEvaluationResult(?array $evaluationResult): static
    {
        $this->evaluationResult = $evaluationResult;
        return $this;
    }

    public function isApproved(): ?bool
    {
        return $this->approved;
    }

    public function getApproved(): ?bool
    {
        return $this->approved;
    }

    public function setApproved(?bool $approved): static
    {
        $this->approved = $approved;
        return $this;
    }

    public function getProcessingLogs(): ?string
    {
        return $this->processingLogs;
    }

    public function setProcessingLogs(?string $processingLogs): static
    {
        $this->processingLogs = $processingLogs;
        return $this;
    }

    public function getCreatedAt(): \DateTimeImmutable
    {
        return $this->createdAt;
    }

    public function getUpdatedAt(): \DateTimeImmutable
    {
        return $this->updatedAt;
    }

    // --- Domain behaviors - encapsulate state transitions ---
    public function markAsProcessing(): void
    {
        $this->status = SubmissionStatus::PROCESSING;
        $this->appendProcessingLog('Status changed to PROCESSING');
    }

    public function markAsFailed(string $reason): void
    {
        $this->status = SubmissionStatus::FAILED;
        $this->appendProcessingLog('Marked as FAILED: ' . $reason);
    }

    public function applyEvaluationResult(array $evaluationResult, bool $approved): void
    {
        $this->evaluationResult = $evaluationResult;
        $this->approved = $approved;
        $this->status = $approved ? SubmissionStatus::APPROVED : SubmissionStatus::REJECTED;
        $this->appendProcessingLog(
            sprintf('Evaluation applied: approved=%s, status=%s', $approved ? 'true' : 'false', $this->status->value)
        );
    }

    public function canBeRetried(): bool
    {
        // Retry allowed for failed submissions, or any non-final state (pending, processing)
        // This matches controller logic: not final OR failed
        return !$this->isFinal() || $this->status === SubmissionStatus::FAILED;
    }

    public function isFinal(): bool
    {
        return $this->status->isFinal();
    }

    public function isFailed(): bool
    {
        return $this->status === SubmissionStatus::FAILED;
    }

    public function appendProcessingLog(string $message): void
    {
        $timestamp = (new \DateTimeImmutable())->format(\DateTimeInterface::ATOM);
        $entry = sprintf('[%s] %s', $timestamp, $message);

        if ($this->processingLogs === null || $this->processingLogs === '') {
            $this->processingLogs = $entry;
        } else {
            $this->processingLogs .= "\n" . $entry;
        }

        // Prevent unbounded growth
        if (strlen($this->processingLogs) > self::MAX_LOG_LENGTH) {
            $this->processingLogs = substr($this->processingLogs, -self::MAX_LOG_LENGTH);
        }
    }

    public function toArray(): array
    {
        return [
            'id' => $this->getIdAsString(),
            'userName' => $this->userName,
            'githubRepoUrl' => $this->githubRepoUrl,
            'challengeId' => $this->challenge?->getIdAsString(),
            'challengeSnapshot' => $this->challengeSnapshot,
            'status' => $this->status->value,
            'approved' => $this->approved,
            'evaluation' => $this->evaluationResult,
            'processingLogs' => $this->processingLogs,
            'createdAt' => $this->createdAt->format(\DateTimeInterface::ATOM),
            'updatedAt' => $this->updatedAt->format(\DateTimeInterface::ATOM),
        ];
    }
}
