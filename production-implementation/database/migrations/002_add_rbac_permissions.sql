-- Migration 002: Add Role-Based Access Control (RBAC) System
-- This migration creates the roles, permissions, and user-role relationships

-- Create roles table
CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    level INTEGER DEFAULT 0, -- Higher level = more permissions
    is_system BOOLEAN DEFAULT false, -- System roles cannot be deleted
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create permissions table
CREATE TABLE IF NOT EXISTS permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    resource VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    scope VARCHAR(20) DEFAULT 'all' CHECK (scope IN ('all', 'own', 'team', 'department')),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create role_permissions junction table
CREATE TABLE IF NOT EXISTS role_permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(role_id, permission_id)
);

-- Add role_id to users table if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'role_id'
    ) THEN
        ALTER TABLE users ADD COLUMN role_id UUID REFERENCES roles(id) ON DELETE SET NULL;
        CREATE INDEX idx_users_role_id ON users(role_id);
        
        -- Create default roles and assign existing users
        INSERT INTO roles (name, description, level, is_system) VALUES
            ('admin', 'System administrator with full access', 100, true),
            ('creator', 'Content creator with access to own resources', 50, true),
            ('viewer', 'Read-only access to assigned resources', 10, true)
        ON CONFLICT (name) DO NOTHING;
        
        -- Assign existing users to 'creator' role by default
        UPDATE users SET role_id = (SELECT id FROM roles WHERE name = 'creator')
        WHERE role_id IS NULL;
        
        -- Make role_id NOT NULL after assignment
        ALTER TABLE users ALTER COLUMN role_id SET NOT NULL;
    END IF;
END $$;

-- Insert default permissions
INSERT INTO permissions (name, resource, action, scope, description) VALUES
    -- User management permissions
    ('user:create', 'user', 'create', 'all', 'Create new users'),
    ('user:read', 'user', 'read', 'all', 'View all users'),
    ('user:read:own', 'user', 'read', 'own', 'View own user profile'),
    ('user:update', 'user', 'update', 'all', 'Update any user'),
    ('user:update:own', 'user', 'update', 'own', 'Update own user profile'),
    ('user:delete', 'user', 'delete', 'all', 'Delete any user'),
    
    -- Candidate management permissions
    ('candidate:create', 'candidate', 'create', 'all', 'Create candidates'),
    ('candidate:read', 'candidate', 'read', 'all', 'View all candidates'),
    ('candidate:read:own', 'candidate', 'read', 'own', 'View own candidates'),
    ('candidate:update', 'candidate', 'update', 'all', 'Update any candidate'),
    ('candidate:update:own', 'candidate', 'update', 'own', 'Update own candidates'),
    ('candidate:delete', 'candidate', 'delete', 'all', 'Delete any candidate'),
    ('candidate:delete:own', 'candidate', 'delete', 'own', 'Delete own candidates'),
    
    -- Application management permissions
    ('application:create', 'application', 'create', 'all', 'Create applications'),
    ('application:read', 'application', 'read', 'all', 'View all applications'),
    ('application:read:own', 'application', 'read', 'own', 'View own applications'),
    ('application:update', 'application', 'update', 'all', 'Update any application'),
    ('application:update:own', 'application', 'update', 'own', 'Update own applications'),
    ('application:delete', 'application', 'delete', 'all', 'Delete any application'),
    ('application:delete:own', 'application', 'delete', 'own', 'Delete own applications'),
    
    -- Interview management permissions (if interviews table exists)
    ('interview:create', 'interview', 'create', 'all', 'Create interviews'),
    ('interview:read', 'interview', 'read', 'all', 'View all interviews'),
    ('interview:read:own', 'interview', 'read', 'own', 'View own interviews'),
    ('interview:update', 'interview', 'update', 'all', 'Update any interview'),
    ('interview:update:own', 'interview', 'update', 'own', 'Update own interviews'),
    ('interview:delete', 'interview', 'delete', 'all', 'Delete any interview'),
    ('interview:delete:own', 'interview', 'delete', 'own', 'Delete own interviews'),
    
    -- Note management permissions (if notes table exists)
    ('note:create', 'note', 'create', 'all', 'Create notes'),
    ('note:read', 'note', 'read', 'all', 'View all notes'),
    ('note:read:own', 'note', 'read', 'own', 'View own notes'),
    ('note:update', 'note', 'update', 'all', 'Update any note'),
    ('note:update:own', 'note', 'update', 'own', 'Update own notes'),
    ('note:delete', 'note', 'delete', 'all', 'Delete any note'),
    ('note:delete:own', 'note', 'delete', 'own', 'Delete own notes'),
    
    -- Document management permissions (if documents table exists)
    ('document:create', 'document', 'create', 'all', 'Upload documents'),
    ('document:read', 'document', 'read', 'all', 'View all documents'),
    ('document:read:own', 'document', 'read', 'own', 'View own documents'),
    ('document:update', 'document', 'update', 'all', 'Update any document'),
    ('document:update:own', 'document', 'update', 'own', 'Update own documents'),
    ('document:delete', 'document', 'delete', 'all', 'Delete any document'),
    ('document:delete:own', 'document', 'delete', 'own', 'Delete own documents'),
    
    -- Tenant management permissions
    ('tenant:create', 'tenant', 'create', 'all', 'Create new tenants'),
    ('tenant:read', 'tenant', 'read', 'all', 'View all tenants'),
    ('tenant:update', 'tenant', 'update', 'all', 'Update any tenant'),
    ('tenant:delete', 'tenant', 'delete', 'all', 'Delete any tenant'),
    ('tenant:read:own', 'tenant', 'read', 'own', 'View own tenant'),
    ('tenant:update:own', 'tenant', 'update', 'own', 'Update own tenant'),
    
    -- System administration permissions
    ('system:configure', 'system', 'configure', 'all', 'Configure system settings'),
    ('system:monitor', 'system', 'monitor', 'all', 'Monitor system performance'),
    ('system:backup', 'system', 'backup', 'all', 'Create system backups'),
    ('system:restore', 'system', 'restore', 'all', 'Restore system from backup'),
    
    -- Audit and reporting permissions
    ('audit:read', 'audit', 'read', 'all', 'View audit logs'),
    ('audit:export', 'audit', 'export', 'all', 'Export audit logs'),
    ('reports:generate', 'report', 'generate', 'all', 'Generate system reports'),
    ('reports:read', 'report', 'read', 'all', 'View system reports'),
    ('reports:export', 'report', 'export', 'all', 'Export system reports'),
    
    -- Profile permissions
    ('profile:read', 'profile', 'read', 'own', 'View own profile'),
    ('profile:update', 'profile', 'update', 'own', 'Update own profile'),
    
    -- API access permissions
    ('api:read', 'api', 'read', 'all', 'Access API endpoints'),
    ('api:create', 'api', 'create', 'all', 'Create API resources'),
    ('api:update', 'api', 'update', 'all', 'Update API resources'),
    ('api:delete', 'api', 'delete', 'all', 'Delete API resources')
ON CONFLICT (name) DO NOTHING;

-- Assign permissions to roles

-- Admin role gets all permissions
DO $$
BEGIN
    -- Get admin role ID
    DECLARE admin_role_id UUID;
    SELECT id INTO admin_role_id FROM roles WHERE name = 'admin';
    
    IF admin_role_id IS NOT NULL THEN
        -- Assign all permissions to admin role
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT admin_role_id, id FROM permissions
        ON CONFLICT (role_id, permission_id) DO NOTHING;
    END IF;
END $$;

-- Creator role permissions
DO $$
BEGIN
    DECLARE creator_role_id UUID;
    SELECT id INTO creator_role_id FROM roles WHERE name = 'creator';
    
    IF creator_role_id IS NOT NULL THEN
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT creator_role_id, id FROM permissions 
        WHERE name IN (
            'candidate:create', 'candidate:read:own', 'candidate:update:own', 'candidate:delete:own',
            'application:create', 'application:read:own', 'application:update:own', 'application:delete:own',
            'interview:create', 'interview:read:own', 'interview:update:own', 'interview:delete:own',
            'note:create', 'note:read:own', 'note:update:own', 'note:delete:own',
            'document:create', 'document:read:own', 'document:update:own', 'document:delete:own',
            'profile:read', 'profile:update',
            'api:read', 'api:create', 'api:update', 'api:delete'
        )
        ON CONFLICT (role_id, permission_id) DO NOTHING;
    END IF;
END $$;

-- Viewer role permissions
DO $$
BEGIN
    DECLARE viewer_role_id UUID;
    SELECT id INTO viewer_role_id FROM roles WHERE name = 'viewer';
    
    IF viewer_role_id IS NOT NULL THEN
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT viewer_role_id, id FROM permissions 
        WHERE name IN (
            'candidate:read:own',
            'application:read:own',
            'interview:read:own',
            'note:read:own',
            'document:read:own',
            'profile:read',
            'api:read'
        )
        ON CONFLICT (role_id, permission_id) DO NOTHING;
    END IF;
END $$;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_roles_name ON roles(name);
CREATE INDEX IF NOT EXISTS idx_roles_level ON roles(level);
CREATE INDEX IF NOT EXISTS idx_permissions_name ON permissions(name);
CREATE INDEX IF NOT EXISTS idx_permissions_resource ON permissions(resource);
CREATE INDEX IF NOT EXISTS idx_permissions_action ON permissions(action);
CREATE INDEX IF NOT EXISTS idx_role_permissions_role_id ON role_permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_role_permissions_permission_id ON role_permissions(permission_id);

-- Create view for user permissions
CREATE OR REPLACE VIEW user_permissions AS
SELECT 
    u.id as user_id,
    u.email,
    r.name as role_name,
    r.level as role_level,
    p.name as permission_name,
    p.resource,
    p.action,
    p.scope,
    p.description as permission_description
FROM users u
JOIN roles r ON u.role_id = r.id
JOIN role_permissions rp ON r.id = rp.role_id
JOIN permissions p ON rp.permission_id = p.id
WHERE u.is_active = true;

-- Create view for role permissions summary
CREATE OR REPLACE VIEW role_permissions_summary AS
SELECT 
    r.id as role_id,
    r.name as role_name,
    r.level as role_level,
    r.description as role_description,
    COUNT(p.id) as permission_count,
    STRING_AGG(p.name, ', ' ORDER BY p.name) as permissions
FROM roles r
LEFT JOIN role_permissions rp ON r.id = rp.role_id
LEFT JOIN permissions p ON rp.permission_id = p.id
GROUP BY r.id, r.name, r.level, r.description
ORDER BY r.level DESC;

-- Create function to check user permission
CREATE OR REPLACE FUNCTION user_has_permission(
    user_uuid UUID,
    permission_name TEXT,
    resource_uuid UUID DEFAULT NULL,
    resource_type TEXT DEFAULT NULL
) RETURNS BOOLEAN AS $$
DECLARE
    has_permission BOOLEAN := FALSE;
    user_role_level INTEGER;
    user_tenant_id UUID;
    resource_tenant_id UUID;
BEGIN
    -- Get user's role level and tenant
    SELECT r.level, u.tenant_id INTO user_role_level, user_tenant_id
    FROM users u
    JOIN roles r ON u.role_id = r.id
    WHERE u.id = user_uuid AND u.is_active = true;
    
    -- Return false if user not found or inactive
    IF user_role_level IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- Admin has all permissions
    IF user_role_level >= 100 THEN
        RETURN TRUE;
    END IF;
    
    -- Check direct permission
    SELECT EXISTS(
        SELECT 1 FROM user_permissions 
        WHERE user_id = user_uuid AND permission_name = permission_name
    ) INTO has_permission;
    
    -- If checking specific resource, verify tenant access
    IF has_permission AND resource_uuid IS NOT NULL AND resource_type IS NOT NULL THEN
        -- Get resource tenant
        EXECUTE format('SELECT tenant_id FROM %I WHERE id = $1', resource_type) 
        INTO resource_tenant_id USING resource_uuid;
        
        -- Deny if resource belongs to different tenant (unless admin)
        IF resource_tenant_id IS NOT NULL AND resource_tenant_id != user_tenant_id THEN
            RETURN FALSE;
        END IF;
        
        -- Check for 'own' scope permissions
        IF permission_name LIKE '%:own' THEN
            -- Verify user owns the resource
            EXECUTE format('SELECT created_by FROM %I WHERE id = $1', resource_type) 
            INTO resource_tenant_id USING resource_uuid;
            
            IF resource_tenant_id != user_uuid THEN
                RETURN FALSE;
            END IF;
        END IF;
    END IF;
    
    RETURN has_permission;
END;
$$ LANGUAGE plpgsql;

-- Create function to get user permissions
CREATE OR REPLACE FUNCTION get_user_permissions(user_uuid UUID)
RETURNS TABLE(permission_name TEXT, resource TEXT, action TEXT, scope TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT p.name, p.resource, p.action, p.scope
    FROM users u
    JOIN roles r ON u.role_id = r.id
    JOIN role_permissions rp ON r.id = rp.role_id
    JOIN permissions p ON rp.permission_id = p.id
    WHERE u.id = user_uuid AND u.is_active = true
    ORDER BY p.resource, p.action, p.scope;
END;
$$ LANGUAGE plpgsql;

-- Add triggers for updated_at columns
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.triggers WHERE trigger_name = 'update_roles_updated_at') THEN
        CREATE TRIGGER update_roles_updated_at 
            BEFORE UPDATE ON roles 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.triggers WHERE trigger_name = 'update_permissions_updated_at') THEN
        CREATE TRIGGER update_permissions_updated_at 
            BEFORE UPDATE ON permissions 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- Add comments for documentation
COMMENT ON TABLE roles IS 'User roles with permission levels';
COMMENT ON TABLE permissions IS 'Granular permissions for resources and actions';
COMMENT ON TABLE role_permissions IS 'Junction table linking roles to permissions';
COMMENT ON VIEW user_permissions IS 'View showing all permissions for active users';
COMMENT ON VIEW role_permissions_summary IS 'Summary of permissions per role';

-- Create constraint to ensure users have roles
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.check_constraints 
        WHERE constraint_name = 'users_must_have_role'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT users_must_have_role 
            CHECK (role_id IS NOT NULL);
    END IF;
END $$;

-- Migration complete
SELECT 'RBAC system migration completed successfully' as status;
