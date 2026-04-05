/**
 * Authentication Middleware - Express.js
 * Provides JWT verification and user context for API endpoints
 */

const AuthService = require('./auth-service');

class AuthMiddleware {
  constructor(authService) {
    this.authService = authService;
  }

  /**
   * Verify JWT token and attach user to request
   */
  authenticate() {
    return async (req, res, next) => {
      try {
        const token = this.extractToken(req);
        if (!token) {
          return res.status(401).json({ 
            error: 'Authentication required',
            code: 'AUTH_TOKEN_MISSING'
          });
        }

        const { user, decoded } = await this.authService.verifyToken(token);
        
        // Attach user and token data to request
        req.user = user;
        req.token = decoded;
        req.tenantId = user.tenantId;
        
        next();
      } catch (error) {
        return res.status(401).json({ 
          error: 'Invalid or expired token',
          code: 'AUTH_TOKEN_INVALID'
        });
      }
    };
  }

  /**
   * Check if user has required role
   */
  requireRole(...allowedRoles) {
    return (req, res, next) => {
      if (!req.user) {
        return res.status(401).json({ 
          error: 'Authentication required',
          code: 'AUTH_REQUIRED'
        });
      }

      if (!allowedRoles.includes(req.user.role)) {
        return res.status(403).json({ 
          error: 'Insufficient permissions',
          code: 'INSUFFICIENT_ROLE',
          required: allowedRoles,
          current: req.user.role
        });
      }

      next();
    };
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

        const hasPermission = await this.checkUserPermission(req.user, permission, req);
        if (!hasPermission) {
          return res.status(403).json({ 
            error: 'Insufficient permissions',
            code: 'INSUFFICIENT_PERMISSION',
            required: permission
          });
        }

        next();
      } catch (error) {
        return res.status(500).json({ 
          error: 'Permission check failed',
          code: 'PERMISSION_CHECK_ERROR'
        });
      }
    };
  }

  /**
   * Ensure user can only access their own tenant data
   */
  requireTenantAccess() {
    return (req, res, next) => {
      if (!req.user) {
        return res.status(401).json({ 
          error: 'Authentication required',
          code: 'AUTH_REQUIRED'
        });
      }

      // Check if requested resource belongs to user's tenant
      const requestedTenantId = req.params.tenantId || req.body.tenantId || req.query.tenantId;
      if (requestedTenantId && requestedTenantId !== req.user.tenantId) {
        return res.status(403).json({ 
          error: 'Access denied: Cross-tenant access not allowed',
          code: 'CROSS_TENANT_ACCESS_DENIED'
        });
      }

      next();
    };
  }

  /**
   * Resource ownership check - user can only access their own resources
   */
  requireOwnership(resourceType) {
    return async (req, res, next) => {
      try {
        if (!req.user) {
          return res.status(401).json({ 
            error: 'Authentication required',
            code: 'AUTH_REQUIRED'
          });
        }

        const resourceId = req.params.id || req.body.id;
        if (!resourceId) {
          return res.status(400).json({ 
            error: 'Resource ID required',
            code: 'RESOURCE_ID_MISSING'
          });
        }

        const isOwner = await this.checkResourceOwnership(req.user, resourceType, resourceId);
        if (!isOwner && req.user.role !== 'admin') {
          return res.status(403).json({ 
            error: 'Access denied: You do not own this resource',
            code: 'RESOURCE_ACCESS_DENIED'
          });
        }

        next();
      } catch (error) {
        return res.status(500).json({ 
          error: 'Ownership check failed',
          code: 'OWNERSHIP_CHECK_ERROR'
        });
      }
    };
  }

  /**
   * Rate limiting middleware for authentication endpoints
   */
  authRateLimit(options = {}) {
    const {
      windowMs = 15 * 60 * 1000, // 15 minutes
      max = 5, // 5 attempts per window
      message = 'Too many authentication attempts, please try again later'
    } = options;

    const attempts = new Map();

    return (req, res, next) => {
      const key = req.ip + ':' + req.path;
      const now = Date.now();
      const windowStart = now - windowMs;

      // Clean old entries
      for (const [k, v] of attempts.entries()) {
        if (v.lastAttempt < windowStart) {
          attempts.delete(k);
        }
      }

      // Check current attempts
      const current = attempts.get(key) || { count: 0, lastAttempt: 0 };
      
      if (current.count >= max && current.lastAttempt > windowStart) {
        return res.status(429).json({ 
          error: message,
          code: 'RATE_LIMIT_EXCEEDED',
          retryAfter: Math.ceil((current.lastAttempt + windowMs - now) / 1000)
        });
      }

      // Update attempts
      attempts.set(key, {
        count: current.count + 1,
        lastAttempt: now
      });

      next();
    };
  }

  /**
   * Extract JWT token from request headers
   */
  extractToken(req) {
    const authHeader = req.headers.authorization;
    if (authHeader && authHeader.startsWith('Bearer ')) {
      return authHeader.substring(7);
    }
    return null;
  }

  /**
   * Check if user has specific permission
   */
  async checkUserPermission(user, permission, req) {
    // Admin has all permissions
    if (user.role === 'admin') {
      return true;
    }

    // Define permission matrix
    const permissions = {
      'creator': [
        'candidate:create',
        'candidate:read:own',
        'candidate:update:own',
        'candidate:delete:own',
        'application:create',
        'application:read:own',
        'application:update:own',
        'application:delete:own'
      ],
      'viewer': [
        'candidate:read:own',
        'application:read:own'
      ]
    };

    const userPermissions = permissions[user.role] || [];
    return userPermissions.includes(permission);
  }

  /**
   * Check if user owns a specific resource
   */
  async checkResourceOwnership(user, resourceType, resourceId) {
    try {
      let resource;
      
      switch (resourceType) {
        case 'candidate':
          resource = await this.authService.db.candidates.findByPk(resourceId);
          break;
        case 'application':
          resource = await this.authService.db.applications.findByPk(resourceId);
          break;
        default:
          return false;
      }

      return resource && resource.tenantId === user.tenantId;
    } catch (error) {
      return false;
    }
  }

  /**
   * Optional authentication - doesn't fail if no token
   */
  optionalAuthenticate() {
    return async (req, res, next) => {
      try {
        const token = this.extractToken(req);
        if (token) {
          const { user, decoded } = await this.authService.verifyToken(token);
          req.user = user;
          req.token = decoded;
          req.tenantId = user.tenantId;
        }
        next();
      } catch (error) {
        // Continue without authentication
        next();
      }
    };
  }

  /**
   * API Key authentication for service-to-service communication
   */
  authenticateApiKey() {
    return async (req, res, next) => {
      try {
        const apiKey = req.headers['x-api-key'];
        if (!apiKey) {
          return res.status(401).json({ 
            error: 'API key required',
            code: 'API_KEY_MISSING'
          });
        }

        const key = await this.authService.db.apiKeys.findOne({
          where: { 
            key: apiKey,
            isActive: true,
            expiresAt: { [this.authService.db.Sequelize.Op.gt]: new Date() }
          },
          include: [{ model: this.authService.db.users, as: 'user' }]
        });

        if (!key) {
          return res.status(401).json({ 
            error: 'Invalid or expired API key',
            code: 'API_KEY_INVALID'
          });
        }

        req.user = key.user;
        req.apiKey = key;
        req.tenantId = key.user.tenantId;
        
        next();
      } catch (error) {
        return res.status(500).json({ 
          error: 'API key authentication failed',
          code: 'API_KEY_AUTH_ERROR'
        });
      }
    };
  }
}

module.exports = AuthMiddleware;
