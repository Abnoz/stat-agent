-- Initialize the commercial licenses database
CREATE DATABASE IF NOT EXISTS commercial_licenses;

-- Connect to the database
\c commercial_licenses;

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- The commercial table will be created by the import script
-- This file ensures the database is properly initialized 