<?php

namespace App\Controller;

use App\Entity\Challenge;
use App\Repository\ChallengeRepository;
use Doctrine\ORM\EntityManagerInterface;
use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Routing\Attribute\Route;
use Symfony\Component\Validator\Validator\ValidatorInterface;

class ChallengeController extends AbstractController
{
    public function __construct(
        private readonly ChallengeRepository $challengeRepository,
        private readonly EntityManagerInterface $entityManager,
        private readonly ValidatorInterface $validator,
    ) {
    }

    #[Route('/api/challenges', name: 'api_challenge_list', methods: ['GET'])]
    public function apiList(): JsonResponse
    {
        $challenges = $this->challengeRepository->findBy([], ['createdAt' => 'DESC']);
        $data = array_map(fn(Challenge $c) => $this->serializeChallenge($c), $challenges);

        return $this->json($data);
    }

    #[Route('/api/challenges', name: 'api_challenge_create', methods: ['POST'])]
    public function apiCreate(Request $request): JsonResponse
    {
        $requestData = $this->parseRequestBody($request);

        $title = $requestData['title'] ?? null;
        $description = $requestData['description'] ?? null;

        if (!$this->hasRequiredFields($title, $description)) {
            return $this->json(['error' => 'title and description required'], 400);
        }

        $challenge = $this->createChallenge($title, $description);

        $validationResponse = $this->validateChallenge($challenge);
        if ($validationResponse !== null) {
            return $validationResponse;
        }

        $this->entityManager->persist($challenge);
        $this->entityManager->flush();

        return $this->json([
            'id' => $challenge->getIdAsString(),
            'title' => $challenge->getTitle(),
        ], 201);
    }

    #[Route('/challenges/new', name: 'challenge_new_form', methods: ['GET'])]
    public function newForm(): Response
    {
        return $this->render('challenge/new.html.twig');
    }

    #[Route('/challenges', name: 'challenge_create_form', methods: ['POST'])]
    public function createFromForm(Request $request): Response
    {
        $title = $request->request->get('title');
        $description = $request->request->get('description');

        if (!is_string($title) || !is_string($description)) {
            $this->addFlash('error', 'Title and description are required');
            return $this->redirectToRoute('challenge_new_form');
        }

        $challenge = $this->createChallenge($title, $description);

        $errors = $this->validator->validate($challenge);
        if (count($errors) > 0) {
            foreach ($errors as $error) {
                $this->addFlash('error', $error->getPropertyPath() . ': ' . $error->getMessage());
            }
            return $this->redirectToRoute('challenge_new_form');
        }

        $this->entityManager->persist($challenge);
        $this->entityManager->flush();

        $this->addFlash('success', 'Challenge created!');
        return $this->redirectToRoute('home');
    }

    private function serializeChallenge(Challenge $challenge): array
    {
        return [
            'id' => $challenge->getIdAsString(),
            'title' => $challenge->getTitle(),
            'description' => $challenge->getDescription(),
            'createdAt' => $challenge->getCreatedAt()->format(\DateTimeInterface::ATOM),
        ];
    }

    private function parseRequestBody(Request $request): array
    {
        $content = $request->getContent();
        if ($content === '') {
            return $request->request->all();
        }

        try {
            $decoded = $request->toArray();
            return is_array($decoded) ? $decoded : [];
        } catch (\Exception) {
            // Fallback to json_decode for empty or invalid JSON
            $decoded = json_decode($content, true);
            if (is_array($decoded)) {
                return $decoded;
            }
            return $request->request->all();
        }
    }

    private function hasRequiredFields(?string $title, ?string $description): bool
    {
        return !empty($title) && !empty($description);
    }

    private function createChallenge(string $title, string $description): Challenge
    {
        $challenge = new Challenge();
        $challenge->setTitle($title);
        $challenge->setDescription($description);

        return $challenge;
    }

    private function validateChallenge(Challenge $challenge): ?JsonResponse
    {
        $errors = $this->validator->validate($challenge);
        if (count($errors) === 0) {
            return null;
        }

        $errorMap = [];
        foreach ($errors as $error) {
            $errorMap[$error->getPropertyPath()] = $error->getMessage();
        }

        return $this->json(['errors' => $errorMap], 400);
    }
}
