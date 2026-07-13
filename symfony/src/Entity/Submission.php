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
    #[ORM\Id]
    #[ORM\Column(type: 'uuid', unique: true)]
    private ?Uuid $id = null;

    #[ORM\Column(length: 180)]
    #[Assert\NotBlank]
    #[Assert\Length(min: 2, max: 180)]
    private ?string $userName = null;

    #[ORM\Column(length: 500)]
    #[Assert\NotBlank]
    #[Assert\Url(requireTld: true)]
    #[Assert\Length(max: 500)]
    private ?string $githubRepoUrl = null;

    #[ORM\ManyToOne(targetEntity: Challenge::class, inversedBy: 'submissions')]
    #[ORM\JoinColumn(nullable: true)]
    private ?Challenge $challenge = null;

    #[ORM\Column(type: Types::TEXT)]
    #[Assert\NotBlank]
    #[Assert\Length(min: 20)]
    private ?string $challengeSnapshot = null;

    #[ORM\Column(enumType: SubmissionStatus::class)]
    private ?SubmissionStatus $status = null;

    #[ORM\Column(type: Types::JSON, nullable: true)]
    private ?array $evaluationResult = null;

    #[ORM\Column(nullable: true)]
    private ?bool $approved = null;

    #[ORM\Column(type: Types::TEXT, nullable: true)]
    private ?string $processingLogs = null;

    #[ORM\Column]
    private ?\DateTimeImmutable $createdAt = null;

    #[ORM\Column]
    private ?\DateTimeImmutable $updatedAt = null;

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

    public function getId(): ?Uuid
    {
        return $this->id;
    }

    public function getUserName(): ?string
    {
        return $this->userName;
    }

    public function setUserName(string $userName): static
    {
        $this->userName = $userName;
        return $this;
    }

    public function getGithubRepoUrl(): ?string
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

    public function setChallenge(?Challenge $challenge): static
    {
        $this->challenge = $challenge;
        if ($challenge) {
            $this->challengeSnapshot = $challenge->getDescription();
        }
        return $this;
    }

    public function getChallengeSnapshot(): ?string
    {
        return $this->challengeSnapshot;
    }

    public function setChallengeSnapshot(string $challengeSnapshot): static
    {
        $this->challengeSnapshot = $challengeSnapshot;
        return $this;
    }

    public function getStatus(): ?SubmissionStatus
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

    public function getCreatedAt(): ?\DateTimeImmutable
    {
        return $this->createdAt;
    }

    public function setCreatedAt(\DateTimeImmutable $createdAt): static
    {
        $this->createdAt = $createdAt;
        return $this;
    }

    public function getUpdatedAt(): ?\DateTimeImmutable
    {
        return $this->updatedAt;
    }

    public function setUpdatedAt(\DateTimeImmutable $updatedAt): static
    {
        $this->updatedAt = $updatedAt;
        return $this;
    }

    public function toArray(): array
    {
        return [
            'id' => $this->id?->toRfc4122(),
            'userName' => $this->userName,
            'githubRepoUrl' => $this->githubRepoUrl,
            'challengeId' => $this->challenge?->getId()?->toRfc4122(),
            'challengeSnapshot' => $this->challengeSnapshot,
            'status' => $this->status?->value,
            'approved' => $this->approved,
            'evaluation' => $this->evaluationResult,
            'processingLogs' => $this->processingLogs,
            'createdAt' => $this->createdAt?->format(\DateTimeInterface::ATOM),
            'updatedAt' => $this->updatedAt?->format(\DateTimeInterface::ATOM),
        ];
    }
}
