<?php

namespace App\Repository;

use App\Entity\Submission;
use App\Enum\SubmissionStatus;
use Doctrine\Bundle\DoctrineBundle\Repository\ServiceEntityRepository;
use Doctrine\Persistence\ManagerRegistry;

/**
 * @extends ServiceEntityRepository<Submission>
 */
class SubmissionRepository extends ServiceEntityRepository
{
    private const DEFAULT_RECENT_LIMIT = 20;
    private const MAX_LIMIT = 100;

    public function __construct(ManagerRegistry $registry)
    {
        parent::__construct($registry, Submission::class);
    }

    public function persist(Submission $entity): void
    {
        $this->getEntityManager()->persist($entity);
    }

    public function saveAndFlush(Submission $entity): void
    {
        $this->persist($entity);
        $this->getEntityManager()->flush();
    }

    public function removeAndFlush(Submission $entity): void
    {
        $this->getEntityManager()->remove($entity);
        $this->getEntityManager()->flush();
    }

    // Backward compat
    public function save(Submission $entity, bool $flush = false): void
    {
        $this->getEntityManager()->persist($entity);
        if ($flush) {
            $this->getEntityManager()->flush();
        }
    }

    public function remove(Submission $entity, bool $flush = false): void
    {
        $this->getEntityManager()->remove($entity);
        if ($flush) {
            $this->getEntityManager()->flush();
        }
    }

    /**
     * @return Submission[]
     */
    public function findRecent(int $limit = self::DEFAULT_RECENT_LIMIT): array
    {
        $validatedLimit = $this->validateLimit($limit);

        return $this->createOrderedQueryBuilder()
            ->setMaxResults($validatedLimit)
            ->getQuery()
            ->getResult();
    }

    /**
     * @return Submission[]
     */
    public function findByStatus(SubmissionStatus $status): array
    {
        return $this->createQueryBuilder('s')
            ->andWhere('s.status = :status')
            ->setParameter('status', $status)
            ->orderBy('s.createdAt', 'DESC')
            ->getQuery()
            ->getResult();
    }

    private function createOrderedQueryBuilder()
    {
        return $this->createQueryBuilder('s')
            ->orderBy('s.createdAt', 'DESC');
    }

    private function validateLimit(int $limit): int
    {
        if ($limit <= 0) {
            throw new \InvalidArgumentException('Limit must be positive');
        }
        return min($limit, self::MAX_LIMIT);
    }
}
