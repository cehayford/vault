/**
 * Role-Based Access Control (RBAC) Service
 * Manages roles, permissions, and access control for the system
 */

class RBACService {
  constructor(database) {
    this.db = database;
    this.setupDefaultRoles();
  }

  /**
   * Initialize default roles and permissions
   */
  async setupDefaultRoles() {
    const defaultRoles = [
      {
        name: 'admin',
        description: 'System administrator with full access',
        level: 100,
        permissions: [
          'user:create', 'user:read', 'user:update', 'user:delete',
          'candidate:create', 'candidate:read', 'candidate:update', 'candidate:delete',
          'candidate:read:all', 'application:create', 'application:read', 'application:update', 'application:delete',
          'application:read:all', 'tenant:create', 'tenant:read', 'tenant:update', 'tenant:delete',
          'system:configure', 'system:monitor', 'audit:read', 'reports:generate'
        ]
      },
      {
        name: 'creator',
        description: 'Content creator with access to own resources',
        level: 50,
        permissions: [
          'candidate:create', 'candidate:read:own', 'candidate:update:own', 'candidate:delete:own',
          'application:create', 'application:read:own', 'application:update:own', 'application:delete:own',
          'profile:read', 'profile:update'
        ]
      },
      {
        name: 'viewer',
        description: 'Read-only access to assigned resources',
        level: 10,
        permissions: [
          'candidate:read:own', 'application:read:own', 'profile:read'
        ]
      }
    ];

    for (const roleData of defaultRoles) {
      const existingRole = await this.db.roles.findOne({ where: { name: roleData.name } });
      if (!existingRole) {
        const role = await this.db.roles.create({
          name: roleData.name,
          description: roleData.description,
          level: roleData.level,
          isSystem: true,
          createdAt: new Date(),
          updatedAt: new Date()
        });

        // Create permissions
        for (const permissionName of roleData.permissions) {
          await this.createPermissionIfNotExists(permissionName);
          const permission = await this.db.permissions.findOne({ where: { name: permissionName } });
          
          await this.db.rolePermissions.create({
            roleId: role.id,
            permissionId: permission.id,
            createdAt: new Date()
          });
        }
      }
    }
  }

  /**
   * Create permission if it doesn't exist
   */
  async createPermissionIfNotExists(permissionName) {
    const existingPermission = await this.db.permissions.findOne({ where: { name: permissionName } });
    if (!existingPermission) {
      const [resource, action, scope = 'all'] = permissionName.split(':');
      
      await this.db.permissions.create({
        name: permissionName,
        resource,
        action,
        scope,
        description: `${action} ${resource} ${scope === 'all' ? '' : scope}`,
        createdAt: new Date(),
        updatedAt: new Date()
      });
    }
  }

  /**
   * Check if user has specific permission
   */
  async hasPermission(userId, permission, context = {}) {
    try {
      const user = await this.db.users.findByPk(userId, {
        include: [
          {
            model: this.db.roles,
            as: 'role',
            include: [
              {
                model: this.db.permissions,
                as: 'permissions'
              }
            ]
          }
        ]
      });

      if (!user || !user.role) {
        return false;
      }

      // Check direct permission
      const hasDirectPermission = user.role.permissions.some(p => p.name === permission);
      if (hasDirectPermission) {
        return true;
      }

      // Check wildcard permissions
      const [resource, action, scope] = permission.split(':');
      const wildcardPermission = `${resource}:${action}:*`;
      const hasWildcardPermission = user.role.permissions.some(p => p.name === wildcardPermission);
      if (hasWildcardPermission) {
        return true;
      }

      // Check resource-level permissions
      if (context.resourceId && context.resourceType) {
        const resourcePermission = `${resource}:${action}:own`;
        const ownsResource = await this.checkResourceOwnership(userId, context.resourceType, context.resourceId);
        
        if (ownsResource && user.role.permissions.some(p => p.name === resourcePermission)) {
          return true;
        }
      }

      return false;
    } catch (error) {
      console.error('Permission check failed:', error);
      return false;
    }
  }

  /**
   * Check if user owns a specific resource
   */
  async checkResourceOwnership(userId, resourceType, resourceId) {
    try {
      let resource;
      
      switch (resourceType) {
        case 'candidate':
          resource = await this.db.candidates.findByPk(resourceId);
          break;
        case 'application':
          resource = await this.db.applications.findByPk(resourceId);
          break;
        case 'user':
          resource = await this.db.users.findByPk(resourceId);
          break;
        default:
          return false;
      }

      if (!resource) {
        return false;
      }

      // Check if user owns the resource (same tenant)
      const user = await this.db.users.findByPk(userId);
      return resource.tenantId === user.tenantId;
    } catch (error) {
      console.error('Ownership check failed:', error);
      return false;
    }
  }

  /**
   * Get all permissions for a user
   */
  async getUserPermissions(userId) {
    try {
      const user = await this.db.users.findByPk(userId, {
        include: [
          {
            model: this.db.roles,
            as: 'role',
            include: [
              {
                model: this.db.permissions,
                as: 'permissions'
              }
            ]
          }
        ]
      });

      if (!user || !user.role) {
        return [];
      }

      return user.role.permissions.map(p => p.name);
    } catch (error) {
      console.error('Failed to get user permissions:', error);
      return [];
    }
  }

  /**
   * Create a new role
   */
  async createRole(roleData, creatorId) {
    try {
      const { name, description, permissions, level = 10 } = roleData;

      // Check if role already exists
      const existingRole = await this.db.roles.findOne({ where: { name } });
      if (existingRole) {
        throw new Error('Role with this name already exists');
      }

      // Create role
      const role = await this.db.roles.create({
        name,
        description,
        level,
        isSystem: false,
        createdBy: creatorId,
        createdAt: new Date(),
        updatedAt: new Date()
      });

      // Assign permissions
      if (permissions && permissions.length > 0) {
        for (const permissionName of permissions) {
          await this.createPermissionIfNotExists(permissionName);
          const permission = await this.db.permissions.findOne({ where: { name: permissionName } });
          
          await this.db.rolePermissions.create({
            roleId: role.id,
            permissionId: permission.id,
            createdAt: new Date()
          });
        }
      }

      return role;
    } catch (error) {
      throw new Error(`Failed to create role: ${error.message}`);
    }
  }

  /**
   * Update user role
   */
  async updateUserRole(userId, newRoleId, updatedBy) {
    try {
      const user = await this.db.users.findByPk(userId);
      if (!user) {
        throw new Error('User not found');
      }

      const newRole = await this.db.roles.findByPk(newRoleId);
      if (!newRole) {
        throw new Error('Role not found');
      }

      // Cannot downgrade system admin unless you're also admin
      if (user.roleId && user.roleId !== newRoleId) {
        const currentRole = await this.db.roles.findByPk(user.roleId);
        if (currentRole.name === 'admin' && newRole.name !== 'admin') {
          const updater = await this.db.users.findByPk(updatedBy);
          const updaterRole = await this.db.roles.findByPk(updater.roleId);
          if (updaterRole.name !== 'admin') {
            throw new Error('Only admins can change admin roles');
          }
        }
      }

      await this.db.users.update({
        roleId: newRoleId,
        updatedAt: new Date()
      }, { where: { id: userId } });

      // Log role change
      await this.db.auditLogs.create({
        userId: updatedBy,
        action: 'USER_ROLE_CHANGED',
        targetType: 'user',
        targetId: userId,
        oldValues: JSON.stringify({ roleId: user.roleId }),
        newValues: JSON.stringify({ roleId: newRoleId }),
        timestamp: new Date()
      });

      return await this.db.users.findByPk(userId, {
        include: [{ model: this.db.roles, as: 'role' }]
      });
    } catch (error) {
      throw new Error(`Failed to update user role: ${error.message}`);
    }
  }

  /**
   * Get all available roles
   */
  async getAllRoles() {
    try {
      return await this.db.roles.findAll({
        include: [
          {
            model: this.db.permissions,
            as: 'permissions',
            attributes: ['id', 'name', 'resource', 'action', 'scope', 'description']
          }
        ],
        order: [['level', 'DESC']]
      });
    } catch (error) {
      throw new Error(`Failed to get roles: ${error.message}`);
    }
  }

  /**
   * Get role by ID
   */
  async getRoleById(roleId) {
    try {
      return await this.db.roles.findByPk(roleId, {
        include: [
          {
            model: this.db.permissions,
            as: 'permissions',
            attributes: ['id', 'name', 'resource', 'action', 'scope', 'description']
          }
        ]
      });
    } catch (error) {
      throw new Error(`Failed to get role: ${error.message}`);
    }
  }

  /**
   * Update role permissions
   */
  async updateRolePermissions(roleId, permissions, updatedBy) {
    try {
      const role = await this.db.roles.findByPk(roleId);
      if (!role) {
        throw new Error('Role not found');
      }

      if (role.isSystem) {
        throw new Error('Cannot modify system roles');
      }

      // Remove existing permissions
      await this.db.rolePermissions.destroy({ where: { roleId } });

      // Add new permissions
      for (const permissionName of permissions) {
        await this.createPermissionIfNotExists(permissionName);
        const permission = await this.db.permissions.findOne({ where: { name: permissionName } });
        
        await this.db.rolePermissions.create({
          roleId,
          permissionId: permission.id,
          createdAt: new Date()
        });
      }

      // Log permission changes
      await this.db.auditLogs.create({
        userId: updatedBy,
        action: 'ROLE_PERMISSIONS_UPDATED',
        targetType: 'role',
        targetId: roleId,
        newValues: JSON.stringify({ permissions }),
        timestamp: new Date()
      });

      return await this.getRoleById(roleId);
    } catch (error) {
      throw new Error(`Failed to update role permissions: ${error.message}`);
    }
  }

  /**
   * Delete role (if not system role and not in use)
   */
  async deleteRole(roleId, deletedBy) {
    try {
      const role = await this.db.roles.findByPk(roleId);
      if (!role) {
        throw new Error('Role not found');
      }

      if (role.isSystem) {
        throw new Error('Cannot delete system roles');
      }

      // Check if role is in use
      const usersWithRole = await this.db.users.count({ where: { roleId } });
      if (usersWithRole > 0) {
        throw new Error('Cannot delete role that is assigned to users');
      }

      await this.db.roles.destroy({ where: { id: roleId } });

      // Log role deletion
      await this.db.auditLogs.create({
        userId: deletedBy,
        action: 'ROLE_DELETED',
        targetType: 'role',
        targetId: roleId,
        oldValues: JSON.stringify({ role: role.name }),
        timestamp: new Date()
      });

      return { success: true, message: 'Role deleted successfully' };
    } catch (error) {
      throw new Error(`Failed to delete role: ${error.message}`);
    }
  }

  /**
   * Get all available permissions
   */
  async getAllPermissions() {
    try {
      return await this.db.permissions.findAll({
        order: [['resource', 'ASC'], ['action', 'ASC'], ['scope', 'ASC']]
      });
    } catch (error) {
      throw new Error(`Failed to get permissions: ${error.message}`);
    }
  }

  /**
   * Check if user can perform action on specific resource
   */
  async canAccessResource(userId, resourceType, action, resourceId = null) {
    try {
      let permission = `${resourceType}:${action}`;
      
      if (resourceId) {
        // Check ownership for scoped permissions
        const ownsResource = await this.checkResourceOwnership(userId, resourceType, resourceId);
        if (ownsResource) {
          permission = `${resourceType}:${action}:own`;
        } else {
          permission = `${resourceType}:${action}:all`;
        }
      }

      return await this.hasPermission(userId, permission, {
        resourceType,
        resourceId
      });
    } catch (error) {
      console.error('Resource access check failed:', error);
      return false;
    }
  }

  /**
   * Get users with specific role
   */
  async getUsersByRole(roleId) {
    try {
      return await this.db.users.findAll({
        where: { roleId },
        attributes: ['id', 'email', 'firstName', 'lastName', 'isActive', 'createdAt'],
        include: [
          {
            model: this.db.roles,
            as: 'role',
            attributes: ['id', 'name', 'description']
          }
        ]
      });
    } catch (error) {
      throw new Error(`Failed to get users by role: ${error.message}`);
    }
  }

  /**
   * Create custom permission
   */
  async createPermission(permissionData) {
    try {
      const { name, resource, action, scope = 'all', description } = permissionData;

      const existingPermission = await this.db.permissions.findOne({ where: { name } });
      if (existingPermission) {
        throw new Error('Permission with this name already exists');
      }

      return await this.db.permissions.create({
        name,
        resource,
        action,
        scope,
        description,
        createdAt: new Date(),
        updatedAt: new Date()
      });
    } catch (error) {
      throw new Error(`Failed to create permission: ${error.message}`);
    }
  }
}

module.exports = RBACService;
