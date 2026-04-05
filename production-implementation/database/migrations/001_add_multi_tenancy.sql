-- Migration 001: Add Multi-Tenancy Support
-- This migration adds tenant isolation to all user-generated data

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create tenants table
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    plan VARCHAR(50) DEFAULT 'basic' CHECK (plan IN ('basic', 'professional', 'enterprise', 'custom')),
    settings JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_by UUID,
    archived_at TIMESTAMP,
    archived_by UUID,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create tenant_settings table
CREATE TABLE IF NOT EXISTS tenant_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    max_users INTEGER DEFAULT 5,
    max_candidates INTEGER DEFAULT 1000,
    max_applications INTEGER DEFAULT 5000,
    storage_quota BIGINT DEFAULT 1073741824, -- 1GB in bytes
    features JSONB DEFAULT '{
        "advanced_search": false,
        "custom_fields": false,
        "api_access": false,
        "sso_integration": false,
        "export_data": true,
        "audit_logs": true
    }',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id)
);

-- Create tenant_permissions table
CREATE TABLE IF NOT EXISTS tenant_permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    resource VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, resource, action)
);

-- Add tenant_id to users table if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE users ADD COLUMN tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
        CREATE INDEX idx_users_tenant_id ON users(tenant_id);
        
        -- Create default tenant for existing users
        INSERT INTO tenants (name, plan, created_by)
        SELECT 'Default Organization', 'basic', id
        FROM users
        WHERE tenant_id IS NULL;
        
        -- Update users to reference their new tenant
        UPDATE users SET tenant_id = subquery.tenant_id
        FROM (
            SELECT u.id, t.id as tenant_id
            FROM users u
            JOIN tenants t ON t.name = 'Default Organization' AND t.created_by = u.id
            WHERE u.tenant_id IS NULL
        ) AS subquery
        WHERE users.id = subquery.id;
    END IF;
END $$;

-- Add tenant_id to candidates table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'candidates' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE candidates ADD COLUMN tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
        CREATE INDEX idx_candidates_tenant_id ON candidates(tenant_id);
        
        -- Migrate existing candidate data
        UPDATE candidates SET tenant_id = (
            SELECT tenant_id FROM users WHERE users.id = candidates.created_by
        ) WHERE tenant_id IS NULL;
        
        -- Make tenant_id NOT NULL after migration
        ALTER TABLE candidates ALTER COLUMN tenant_id SET NOT NULL;
    END IF;
END $$;

-- Add tenant_id to applications table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'applications' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE applications ADD COLUMN tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
        CREATE INDEX idx_applications_tenant_id ON applications(tenant_id);
        
        -- Migrate existing application data
        UPDATE applications SET tenant_id = (
            SELECT tenant_id FROM candidates WHERE candidates.id = applications.candidate_id
        ) WHERE tenant_id IS NULL;
        
        -- Make tenant_id NOT NULL after migration
        ALTER TABLE applications ALTER COLUMN tenant_id SET NOT NULL;
    END IF;
END $$;

-- Add tenant_id to interviews table if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'interviews') THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'interviews' AND column_name = 'tenant_id'
        ) THEN
            ALTER TABLE interviews ADD COLUMN tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
            CREATE INDEX idx_interviews_tenant_id ON interviews(tenant_id);
            
            -- Migrate existing interview data
            UPDATE interviews SET tenant_id = (
                SELECT tenant_id FROM applications WHERE applications.id = interviews.application_id
            ) WHERE tenant_id IS NULL;
            
            -- Make tenant_id NOT NULL after migration
            ALTER TABLE interviews ALTER COLUMN tenant_id SET NOT NULL;
        END IF;
    END IF;
END $$;

-- Add tenant_id to notes table if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'notes') THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'notes' AND column_name = 'tenant_id'
        ) THEN
            ALTER TABLE notes ADD COLUMN tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
            CREATE INDEX idx_notes_tenant_id ON notes(tenant_id);
            
            -- Migrate existing note data based on creator
            UPDATE notes SET tenant_id = (
                SELECT tenant_id FROM users WHERE users.id = notes.created_by
            ) WHERE tenant_id IS NULL;
            
            -- Make tenant_id NOT NULL after migration
            ALTER TABLE notes ALTER COLUMN tenant_id SET NOT NULL;
        END IF;
    END IF;
END $$;

-- Add tenant_id to documents table if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'documents') THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'documents' AND column_name = 'tenant_id'
        ) THEN
            ALTER TABLE documents ADD COLUMN tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
            CREATE INDEX idx_documents_tenant_id ON documents(tenant_id);
            
            -- Migrate existing document data based on uploader
            UPDATE documents SET tenant_id = (
                SELECT tenant_id FROM users WHERE users.id = documents.uploaded_by
            ) WHERE tenant_id IS NULL;
            
            -- Make tenant_id NOT NULL after migration
            ALTER TABLE documents ALTER COLUMN tenant_id SET NOT NULL;
        END IF;
    END IF;
END $$;

-- Add tenant_id to tags table if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tags') THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'tags' AND column_name = 'tenant_id'
        ) THEN
            ALTER TABLE tags ADD COLUMN tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
            CREATE INDEX idx_tags_tenant_id ON tags(tenant_id);
            
            -- Migrate existing tag data based on creator
            UPDATE tags SET tenant_id = (
                SELECT tenant_id FROM users WHERE users.id = tags.created_by
            ) WHERE tenant_id IS NULL;
            
            -- Make tenant_id NOT NULL after migration
            ALTER TABLE tags ALTER COLUMN tenant_id SET NOT NULL;
        END IF;
    END IF;
END $$;

-- Create Row Level Security (RLS) for PostgreSQL
DO $$
BEGIN
    -- Enable RLS on all tenant-isolated tables
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'candidates') THEN
        ALTER TABLE candidates ENABLE ROW LEVEL SECURITY;
        
        -- Drop existing policy if it exists
        DROP POLICY IF EXISTS tenant_isolation_policy ON candidates;
        
        -- Create tenant isolation policy
        CREATE POLICY tenant_isolation_policy ON candidates
            FOR ALL
            TO authenticated_users
            USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'applications') THEN
        ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
        
        DROP POLICY IF EXISTS tenant_isolation_policy ON applications;
        
        CREATE POLICY tenant_isolation_policy ON applications
            FOR ALL
            TO authenticated_users
            USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'interviews') THEN
        ALTER TABLE interviews ENABLE ROW LEVEL SECURITY;
        
        DROP POLICY IF EXISTS tenant_isolation_policy ON interviews;
        
        CREATE POLICY tenant_isolation_policy ON interviews
            FOR ALL
            TO authenticated_users
            USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'notes') THEN
        ALTER TABLE notes ENABLE ROW LEVEL SECURITY;
        
        DROP POLICY IF EXISTS tenant_isolation_policy ON notes;
        
        CREATE POLICY tenant_isolation_policy ON notes
            FOR ALL
            TO authenticated_users
            USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'documents') THEN
        ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
        
        DROP POLICY IF EXISTS tenant_isolation_policy ON documents;
        
        CREATE POLICY tenant_isolation_policy ON documents
            FOR ALL
            TO authenticated_users
            USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tags') THEN
        ALTER TABLE tags ENABLE ROW LEVEL SECURITY;
        
        DROP POLICY IF EXISTS tenant_isolation_policy ON tags;
        
        CREATE POLICY tenant_isolation_policy ON tags
            FOR ALL
            TO authenticated_users
            USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
    END IF;
END $$;

-- Create audit_logs table for tracking tenant operations
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(100),
    target_id UUID,
    old_values JSONB,
    new_values JSONB,
    metadata JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for audit_logs
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_id ON audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);

-- Create security_logs table for tracking security events
CREATE TABLE IF NOT EXISTS security_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    metadata JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    severity VARCHAR(20) DEFAULT 'MEDIUM' CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for security_logs
CREATE INDEX IF NOT EXISTS idx_security_logs_user_id ON security_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_security_logs_tenant_id ON security_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_security_logs_event_type ON security_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_security_logs_severity ON security_logs(severity);
CREATE INDEX IF NOT EXISTS idx_security_logs_timestamp ON security_logs(timestamp);

-- Create trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for tables with updated_at columns
DO $$
BEGIN
    -- tenants table
    IF NOT EXISTS (SELECT 1 FROM information_schema.triggers WHERE trigger_name = 'update_tenants_updated_at') THEN
        CREATE TRIGGER update_tenants_updated_at 
            BEFORE UPDATE ON tenants 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    -- tenant_settings table
    IF NOT EXISTS (SELECT 1 FROM information_schema.triggers WHERE trigger_name = 'update_tenant_settings_updated_at') THEN
        CREATE TRIGGER update_tenant_settings_updated_at 
            BEFORE UPDATE ON tenant_settings 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- Create function to set tenant context
CREATE OR REPLACE FUNCTION set_tenant_context(tenant_uuid UUID)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', tenant_uuid::TEXT, true);
END;
$$ LANGUAGE plpgsql;

-- Create function to clear tenant context
CREATE OR REPLACE FUNCTION clear_tenant_context()
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', '', true);
END;
$$ LANGUAGE plpgsql;

-- Create view for tenant statistics
CREATE OR REPLACE VIEW tenant_statistics AS
SELECT 
    t.id,
    t.name,
    t.plan,
    t.is_active,
    COUNT(DISTINCT u.id) as total_users,
    COUNT(DISTINCT CASE WHEN u.is_active = true THEN u.id END) as active_users,
    COUNT(DISTINCT c.id) as total_candidates,
    COUNT(DISTINCT a.id) as total_applications,
    t.created_at,
    t.updated_at
FROM tenants t
LEFT JOIN users u ON t.id = u.tenant_id
LEFT JOIN candidates c ON t.id = c.tenant_id
LEFT JOIN applications a ON t.id = a.tenant_id
GROUP BY t.id, t.name, t.plan, t.is_active, t.created_at, t.updated_at;

-- Grant necessary permissions (adjust based on your database user)
-- GRANT USAGE ON SCHEMA public TO your_app_user;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_app_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_app_user;

-- Create indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_candidates_created_by_tenant ON candidates(created_by, tenant_id);
CREATE INDEX IF NOT EXISTS idx_applications_candidate_id_tenant ON applications(candidate_id, tenant_id);
CREATE INDEX IF NOT EXISTS idx_applications_created_by_tenant ON applications(created_by, tenant_id);

-- Add comments for documentation
COMMENT ON TABLE tenants IS 'Multi-tenant organization table';
COMMENT ON TABLE tenant_settings IS 'Per-tenant configuration and limits';
COMMENT ON TABLE tenant_permissions IS 'Per-tenant permission overrides';
COMMENT ON TABLE audit_logs IS 'Audit trail for all data changes';
COMMENT ON TABLE security_logs IS 'Security event logging';

-- Migration complete
SELECT 'Multi-tenancy migration completed successfully' as status;
