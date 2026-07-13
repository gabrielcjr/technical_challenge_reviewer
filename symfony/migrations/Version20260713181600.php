<?php

declare(strict_types=1);

namespace DoctrineMigrations;

use Doctrine\DBAL\Schema\Schema;
use Doctrine\Migrations\AbstractMigration;

/**
 * Auto-generated Migration: Please modify to your needs!
 */
final class Version20260713181600 extends AbstractMigration
{
    public function getDescription(): string
    {
        return '';
    }

    public function up(Schema $schema): void
    {
        // this up() migration is auto-generated, please modify it to your needs
        $this->addSql('CREATE TABLE challenges (id UUID NOT NULL, title VARCHAR(255) NOT NULL, description TEXT NOT NULL, created_at TIMESTAMP(0) WITHOUT TIME ZONE NOT NULL, PRIMARY KEY (id))');
        $this->addSql('CREATE TABLE submissions (id UUID NOT NULL, user_name VARCHAR(180) NOT NULL, github_repo_url VARCHAR(500) NOT NULL, challenge_snapshot TEXT NOT NULL, status VARCHAR(255) NOT NULL, evaluation_result JSON DEFAULT NULL, approved BOOLEAN DEFAULT NULL, processing_logs TEXT DEFAULT NULL, created_at TIMESTAMP(0) WITHOUT TIME ZONE NOT NULL, updated_at TIMESTAMP(0) WITHOUT TIME ZONE NOT NULL, challenge_id UUID DEFAULT NULL, PRIMARY KEY (id))');
        $this->addSql('CREATE INDEX IDX_3F6169F798A21AC6 ON submissions (challenge_id)');
        $this->addSql('ALTER TABLE submissions ADD CONSTRAINT FK_3F6169F798A21AC6 FOREIGN KEY (challenge_id) REFERENCES challenges (id) NOT DEFERRABLE');
    }

    public function down(Schema $schema): void
    {
        // this down() migration is auto-generated, please modify it to your needs
        $this->addSql('ALTER TABLE submissions DROP CONSTRAINT FK_3F6169F798A21AC6');
        $this->addSql('DROP TABLE challenges');
        $this->addSql('DROP TABLE submissions');
    }
}
