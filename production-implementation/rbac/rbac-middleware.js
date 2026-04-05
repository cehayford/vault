/**
 * RBAC Middleware - Express.js
 * Provides role-based access control for API endpoints
 */

const RBACService = require('./rbac-service');

class RBACMiddleware {
  constructor(rbacService) {
    this.rbacService = rbacService;
  }

  /**
   * Check if user has specific permission
   */
  requirePermission(permission) {
    return async (req, res, next) => {
      try {
        if (!req.user) {
          return res.status(401).json({
            error: 'Authentication required',
            code: 'AUTH_REQUIRED'
          });
        }

        const hasPermission = await this.rbacService.hasPermission(
          req.user.id,
          permission,
          {
            resourceType: this.getResourceTypeFromRequest(req),
            resourceId: req.params.id || req.body.id
          }
        );

        if (!hasPermission) {
          // Get user permissions for debugging
          const userPermissions = await this.rbacService.getUserPermissions(req.user.id);
          
          return res.status(403).json({
            error: 'Insufficient permissions',
            code: 'INSUFFICIENT_PERMISSIONS',
            required: permission,
            userPermissions,
            userRole: req.user.role?.name
          });
        }

        next();
      } catch (error) {
        console.error('Permission check failed:', error);
        return res.status(500).json({
          error: 'Permission check failed',
          code: 'PERMISSION_CHECK_ERROR'
        });
      }
    };
  }

  /**
   * Check if user has any of the specified permissions
   */
  requireAnyPermission(...permissions) {
    return async (req, res, next) => {
      try {
        if (!req.user) {
          return res.status(401).json({
            error: 'Authentication required',
            code: 'AUTH_REQUIRED'
          });
        }

        let hasAnyPermission = false;
        let grantedPermission = null;

        for (const permission of permissions) {
          const hasPermission = await this.rbacService.hasPermission(
            req.user.id,
            permission,
            {
              resourceType: this.getResourceTypeFromRequest(req),
              resourceId: req.params.id || req.body.id
            }
          );

          if (hasPermission) {
            hasAnyPermission = true;
            grantedPermission = permission;
            break;
          }
        }

        if (!hasAnyPermission) {
          const userPermissions = await this.rbacService.getUserPermissions(req.user.id);
          
          return res.status(403).json({
            error: 'Insufficient permissions',
            code: 'INSUFFICIENT_PERMISSIONS',
            required: permissions,
            userPermissions,
            userRole: req.user.role?.name
          });
        }

        // Add granted permission to request for potential use later
        req.grantedPermission = grantedPermission;
        next();
      } catch (error) {
        console.error('Permission check failed:', error);
        return res.status(500).json({
          error: 'Permission check failed',
          code: 'PERMISSION_CHECK_ERROR'
        });
      }
    };
  }

  /**
   * Check if user has all specified permissions
   */
  requireAllPermissions(...permissions) {
    return async (req, res, next) => {
      try {
        if (!req.user) {
          return res.status(401).json({
            error: 'Authentication required',
            code: 'AUTH_REQUIRED'
          });
        }

        const missingPermissions = [];
        const userPermissions = await this.rbacService.getUserPermissions(req.user.id);

        for (const permission of permissions) {
          const hasPermission = await this.rbacService.hasPermission(
            req.user.id,
            permission,
            {
              resourceType: this.getResourceTypeFromRequest(req),
              resourceId: req.params.id || req.body.id
            }
          );

          if (!hasPermission) {
            missingPermissions.push(permission);
          }
        }

        if (missingPermissions.length > 0) {
          return res.status(403).json({
            error: 'Insufficient permissions',
            code: 'MISSING_PERMISSIONS',
            required: permissions,
            missing: missingPermissions,
            userPermissions,
            userRole: req.user.role?.name
          });
        }

        next();
      } catch (error) {
        console.error('Permission check failed:', error);
        return res.status(500).json({
          error: 'Permission check failed',
          code: 'PERMISSION_CHECK_ERROR'
        });
      }
    };
  }

  /**
   * Check if user has specific role
   */
  requireRole(...roles) {
    return (req, res, next) => {
      if (!req.user) {
        return res.status(401).json({
          error: 'Authentication required',
          code: 'AUTH_REQUIRED'
        });
      }

      const userRole = req.user.role?.name;
      if (!userRole || !roles.includes(userRole)) {
        return res.status(403).json({
          error: 'Insufficient role permissions',
          code: 'INSUFFICIENT_ROLE',
          required: roles,
          current: userRole
        });
      }

      next();
    };
  }

  /**
   * Check if user has minimum role level
   */
  requireMinRoleLevel(minLevel) {
    return (req, res, next) => {
      if (!req.user) {
        return res.status(401).json({
          error: 'Authentication required',
          code: 'AUTH_REQUIRED'
        });
      }

      const userRoleLevel = req.user.role?.level || 0;
      if (userRoleLevel < minLevel) {
        return res.status(403).json({
          error: 'Insufficient role level',
          code: 'INSUFFICIENT_ROLE_LEVEL',
          required: minLevel,
          current: userRoleLevel,
          currentRole: req.user.role?.name
        });
      }

      next();
    };
  }

  /**
   * Check resource ownership or admin access
   */
  requireOwnershipOrAdmin(resourceType) {
    return async (req, res, next) => {
      try {
        if (!req.user) {
          return res.status(401).json({
            error: 'Authentication required',
            code: 'AUTH_REQUIRED'
          });
        }

        // Admin can access everything
        if (req.user.role?.name === 'admin') {
          return next();
        }

        const resourceId = req.params.id || req.body.id;
        if (!resourceId) {
          return res.status(400).json({
            error: 'Resource ID required',
            code: 'RESOURCE_ID_REQUIRED'
          });
        }

        const ownsResource = await this.rbacService.checkResourceOwnership(
          req.user.id,
          resourceType,
          resourceId
        );

        if (!ownsResource) {
          return res.status(403).json({
            error: 'Access denied: You do not own this resource',
            code: 'RESOURCE_OWNERSHIP_REQUIRED',
            resourceType,
            resourceId
          });
        }

        next();
      } catch (error) {
        console.error('Ownership check failed:', error);
        return res.status(500).json({
          error: 'Ownership check failed',
          code: 'OWNERSHIP_CHECK_ERROR'
        });
      }
    };
  }

  /**
   * Check tenant access (prevent cross-tenant access)
   */
  requireTenantAccess() {
    return (req, res, next) => {
      if (!req.user) {
        return res.status(401).json({
          error: 'Authentication required',
          code: 'AUTH_REQUIRED'
        });
      }

      // Admin can access all tenants
      if (req.user.role?.name === 'admin') {
        return next();
      }

      const userTenantId = req.user.tenantId;
      const requestedTenantId = req.params.tenantId || 
                               req.body.tenantId || 
                               req.query.tenantId;

      if (requestedTenantId && requestedTenantId !== userTenantId) {
        return res.status(403).json({
          error: 'Cross-tenant access denied',
          code: 'CROSS_TENANT_ACCESS_DENIED',
          userTenantId,
          requestedTenantId
        });
      }

      // Add tenant filter to queries
      req.tenantFilter = { tenantId: userTenantId };
      next();
    };
  }

  /**
   * Dynamic permission check based on request method
   */
  requireResourcePermission(resourceType) {
    return async (req, res, next) => {
      try {
        if (!req.user) {
          return res.status(401).json({
            error: 'Authentication required',
            code: 'AUTH_REQUIRED'
          });
        }

        const method = req.method.toLowerCase();
        const resourceId = req.params.id || req.body.id;
        
        let action;
        switch (method) {
          case 'get':
            action = resourceId ? 'read' : 'read:all';
            break;
          case 'post':
            action = 'create';
            break;
          case 'put':
          case 'patch':
            action = 'update';
            break;
          case 'delete':
            action = 'delete';
            break;
          default:
            return res.status(405).json({
              error: 'Method not allowed',
              code: 'METHOD_NOT_ALLOWED'
            });
        }

        const canAccess = await this.rbacService.canAccessResource(
          req.user.id,
          resourceType,
          action,
          resourceId
        );

        if (!canAccess) {
          const userPermissions = await this.rbacService.getUserPermissions(req.user.id);
          
          return res.status(403).json({
            error: 'Insufficient permissions',
            code: 'RESOURCE_ACCESS_DENIED',
            resourceType,
            action,
            resourceId,
            userPermissions,
            userRole: req.user.role?.name
          });
        }

        next();
      } catch (error) {
        console.error('Resource permission check failed:', error);
        return res.status(500).json({
          error: 'Permission check failed',
          code: 'PERMISSION_CHECK_ERROR'
        });
      }
    };
  }

  /**
   * Check if user can access specific tenant
   */
  requireTenantMembership(tenantIdParam = 'tenantId') {
    return async (req, res, next) => {
      try {
        if (!req.user) {
          return res.status(401).json({
            error: 'Authentication required',
            code: 'AUTH_REQUIRED'
          });
        }

        const requestedTenantId = req.params[tenantIdParam] || 
                                 req.body[tenantIdParam] || 
                                 req.query[tenantIdParam];

        if (!requestedTenantId) {
          return res.status(400).json({
            error: 'Tenant ID required',
            code: 'TENANT_ID_REQUIRED'
          });
        }

        // Admin can access any tenant
        if (req.user.role?.name === 'admin') {
          return next();
        }

        // Check if user belongs to the tenant
        if (requestedTenantId !== req.user.tenantId) {
          return res.status(403).json({
            error: 'Tenant access denied',
            code: 'TENANT_ACCESS_DENIED',
            userTenantId: req.user.tenantId,
            requestedTenantId
          });
        }

        next();
      } catch (error) {
        console.error('Tenant membership check failed:', error);
        return res.status(500).json({
          error: 'Tenant check failed',
          code: 'TENANT_CHECK_ERROR'
        });
      }
    };
  }

  /**
   * Add user permissions to request object
   */
  loadUserPermissions() {
    return async (req, res, next) => {
      try {
        if (req.user) {
          req.userPermissions = await this.rbacService.getUserPermissions(req.user.id);
        }
        next();
      } catch (error) {
        console.error('Failed to load user permissions:', error);
        next(); // Continue without permissions
      }
    };
  }

  /**
   * Filter query results based on user permissions
   */
  filterByPermissions(resourceType) {
    return async (req, res, next) => {
      try {
        if (!req.user) {
          return res.status(401).json({
            error: 'Authentication required',
            code: 'AUTH_REQUIRED'
          });
        }

        // Admin can see all
        if (req.user.role?.name === 'admin') {
          return next();
        }

        // Add tenant filter for non-admin users
        if (!req.query || !req.query.where) {
          req.query = req.query || {};
          req.query.where = req.query.where || {};
        }

        req.query.where.tenantId = req.user.tenantId;

        // If user can only read own resources, add owner filter
        const canReadAll = await this.rbacService.hasPermission(
          req.user.id,
          `${resourceType}:read:all`
        );

        if (!canReadAll) {
          const canReadOwn = await this.rbacService.hasPermission(
            req.user.id,
            `${resourceType}:read:own`
          );

          if (canReadOwn) {
            req.query.where.createdBy = req.user.id;
          } else {
            // User has no read permissions
            return res.status(403).json({
              error: 'No read permissions for this resource',
              code: 'NO_READ_PERMISSIONS',
              resourceType
            });
          }
        }

        next();
      } catch (error) {
        console.error('Permission filter failed:', error);
        return res.status(500).json({
          error: 'Permission filtering failed',
          code: 'PERMISSION_FILTER_ERROR'
        });
      }
    };
  }

  /**
   * Extract resource type from request
   */
  getResourceTypeFromRequest(req) {
    const path = req.path;
    const segments = path.split('/').filter(s => s && s !== 'api');
    
    // Common patterns: /api/candidates, /api/applications, /api/users
    if (segments.length > 0) {
      const resource = segments[0];
      // Remove trailing 's' for singular form if needed
      return resource.endsWith('s') ? resource.slice(0, -1) : resource;
    }
    
    return 'unknown';
  }

  /**
   * Rate limiting based on user role
   */
  roleBasedRateLimit(options = {}) {
    const {
      admin = { windowMs: 15 * 60 * 1000, max: 1000 },
      creator = { windowMs: 15 * 60 * 1000, max: 100 },
      viewer = { windowMs: 15 * 60 * 1000, max: 50 },
      default: { windowMs: 15 * 60 * 1000, max: 30 }
    } = options;

    const attempts = new Map();

    return (req, res, next) => {
      if (!req.user) {
        return next();
      }

      const userRole = req.user.role?.name || 'default';
      const config = options[userRole] || options.default || default;
      
      const key = req.user.id + ':' + req.path;
      const now = Date.now();
      const windowStart = now - config.windowMs;

      // Clean old entries
      for (const [k, v] of attempts.entries()) {
        if (v.lastAttempt < windowStart) {
          attempts.delete(k);
        }
      }

      // Check current attempts
      const current = attempts.get(key) || { count: 0, lastAttempt: 0 };
      
      if (current.count >= config.max && current.lastAttempt > windowStart) {
        return res.status(429).json({
          error: 'Rate limit exceeded',
          code: 'RATE_LIMIT_EXCEEDED',
          retryAfter: Math.ceil((current.lastAttempt + config.windowMs - now) / 1000),
          limit: config.max,
          windowMs: config.windowMs
        });
      }

      // Update attempts
      attempts.set(key, {
        count: current.count + 1,
        lastAttempt: now
      });

      // Add rate limit headers
      res.set({
        'X-RateLimit-Limit': config.max,
        'X-RateLimit-Remaining': Math.max(0, config.max - current.count - 1),
        'X-RateLimit-Reset': new Date(now + config.windowMs)
      });

      next();
    };
  }
}

module.exports = RBACMiddleware;
