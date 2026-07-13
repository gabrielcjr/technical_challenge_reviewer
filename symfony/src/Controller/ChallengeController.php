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
    #[Route('/api/challenges', name: 'api_challenge_list', methods: ['GET'])]
    public function list(ChallengeRepository $repo): JsonResponse
    {
        $challenges = $repo->findBy([], ['createdAt' => 'DESC']);
        $data = array_map(fn(Challenge $c) => [
            'id' => $c->getId()->toRfc4122(),
            'title' => $c->getTitle(),
            'description' => $c->getDescription(),
            'createdAt' => $c->getCreatedAt()->format(\DateTimeInterface::ATOM),
        ], $challenges);

        return $this->json($data);
    }

    #[Route('/api/challenges', name: 'api_challenge_create', methods: ['POST'])]
    public function create(Request $request, EntityManagerInterface $em, ValidatorInterface $validator): JsonResponse
    {
        $data = json_decode($request->getContent(), true);
        if (!$data) {
            $data = $request->request->all();
        }

        $title = $data['title'] ?? null;
        $description = $data['description'] ?? null;

        if (!$title || !$description) {
            return $this->json(['error' => 'title and description required'], 400);
        }

        $challenge = new Challenge();
        $challenge->setTitle($title);
        $challenge->setDescription($description);

        $errors = $validator->validate($challenge);
        if (count($errors) > 0) {
            $errs = [];
            foreach ($errors as $e) {
                $errs[$e->getPropertyPath()] = $e->getMessage();
            }
            return $this->json(['errors' => $errs], 400);
        }

        $em->persist($challenge);
        $em->flush();

        return $this->json([
            'id' => $challenge->getId()->toRfc4122(),
            'title' => $challenge->getTitle(),
        ], 201);
    }

    #[Route('/challenges/new', name: 'challenge_new_form', methods: ['GET'])]
    public function newForm(): Response
    {
        return $this->render('challenge/new.html.twig');
    }

    #[Route('/challenges', name: 'challenge_create_form', methods: ['POST'])]
    public function createChallengeForm(Request $request, EntityManagerInterface $em, ValidatorInterface $validator): Response
    {
        $title = $request->request->get('title');
        $description = $request->request->get('description');

        $challenge = new Challenge();
        $challenge->setTitle($title);
        $challenge->setDescription($description);

        $errors = $validator->validate($challenge);
        if (count($errors) > 0) {
            foreach ($errors as $error) {
                $this->addFlash('error', $error->getPropertyPath() . ': ' . $error->getMessage());
            }
            return $this->redirectToRoute('challenge_new_form');
        }

        $em->persist($challenge);
        $em->flush();

        $this->addFlash('success', 'Challenge created!');
        return $this->redirectToRoute('home');
    }
}
