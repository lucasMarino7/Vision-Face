-- usado para inicializar as extensões do PostgreSQL para pesquisa com vetores.

-- pgvector: Vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;


-- Verify extensions are installed
DO $$
BEGIN
    RAISE NOTICE 'Extensions installed:';
    RAISE NOTICE '  - vector: %', (SELECT extversion FROM pg_extension WHERE extname = 'vector');
END $$;