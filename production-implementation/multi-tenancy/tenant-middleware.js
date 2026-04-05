/**
 * Tenant Middleware - Express.js
 * Ensures tenant isolation and prevents cross-tenant data access
 */

const TenantService = require('./tenant-service');

class TenantMiddleware {
  constructor(tenantService) {
    this.tenantService = tenantService;
  }

  /**
   * Set tenant context for the request
   */
  setTenantContext() {
    return async (req, res, next) => {
      try {
        if (!req.user) {
          return res.status(401).json({
            error: 'Authentication required',
            code: 'AUTH_REQUIRED'
          });
        }

        // Admin can switch tenants (with tenantId parameter)
        if (req.user.role?.name === 'admin' && req.headers['x-tenant-id']) {
          req.tenantId = req.headers['x-tenant-id'];
        } else {
          // Regular users can only access their own tenant
          req.tenantId = req.user.tenantId;
        }

        // Verify tenant exists and is active
        const tenant = await this.tenantService.db.tenants.findByPk(req.tenantId);
        if (!tenant) {
          return res.status(404).json({
            error: 'Tenant not found',
            code: 'TENANT_NOT_FOUND'
          });
        }

        if (!tenant.isActive) {
          return res.status(403).json({
            error: 'Tenant is not active',
            code: 'TENANT_INACTIVE'
          });
        }

        // Set tenant context in database
        await this.tenantService.setTenantContext(req.tenantId);

        // Add tenant filter to all queries
        req.tenantFilter = { tenantId: req.tenantId };

        next();
      } catch (error) {
        console.error('Tenant context setup failed:', error);
        return res.status(500).json({
          error: 'Tenant context setup failed',
          code: 'TENANT_CONTEXT_ERROR'
        });
      }
    };
  }

  /**
   * Validate tenant access for specific operations
   */
  validateTenantAccess() {
    return async (req, res, next) => {
      try {
        if (!req.user) {
          return res.status(401).json({
            error: 'Authentication required',
            code: 'AUTH_REQUIRED'
          });
        }

        // Extract tenant ID from various sources
        const requestedTenantId = req.params.tenantId || 
                                 req.body.tenantId || 
                                 req.query.tenantId ||
                                 req.headers['x-tenant-id'];

        // Admin can access any tenant
        if (req.user.role?.name === 'admin') {
          if (requestedTenantId) {
            req.tenantId = requestedTenantId;
          }
          return next();
        }

        // Non-admin users can only access their own tenant
        if (requestedTenantId && requestedTenantId !== req.user.tenantId) {
          await this.logSecurityEvent('CROSS_TENANT_ACCESS_ATTEMPT', req.user.id, {
            userTenantId: req.user.tenantId,
            requestedTenantId,
            path: req.path,
            method: req.method,
            ipAddress: req.ip
          });

          return res.status(403).json({
            error: 'Cross-tenant access denied',
            code: 'CROSS_TENANT_ACCESS_DENIED',
            userTenantId: req.user.tenantId,
            requestedTenantId
          });
        }

        req.tenantId = req.user.tenantId;
        next();
      } catch (error) {
        console.error('Tenant access validation failed:', error);
        return res.status(500).json({
          error: 'Tenant access validation failed',
          code: 'TENANT_ACCESS_ERROR'
        });
      }
    };
  }

  /**
   * Check tenant resource limits
   */
  checkTenantLimits(resourceType) {
    return async (req, res, next) => {
      try {
        if (!req.user || !req.tenantId) {
          return next(); // Skip if no tenant context
        }

        // Admin bypasses limits
        if (req.user.role?.name === 'admin') {
          return next();
        }

        const limits = await this.tenantService.checkTenantLimits(req.tenantId);
        
        if (limits.anyExceeded) {
          const relevantLimit = limits.limits[resourceType];
          if (relevantLimit && relevantLimit.exceeded) {
            return res.status(429).json({
              error: 'Tenant resource limit exceeded',
              code: 'TENANT_LIMIT_EXCEEDED',
              resource: resourceType,
              current: relevantLimit.current,
              max: relevantLimit.max,
              message: `Your ${resourceType} limit (${relevantLimit.max}) has been reached. Please upgrade your plan.`
            });
          }
        }

        next();
      } catch (error) {
        console.error('Tenant limit check failed:', error);
        // Don't block the request if limit check fails
        next();
      }
    };
  }

  /**
   * Add tenant filtering to database queries
   */
  filterByTenant() {
    return (req, res, next) => {
      if (!req.tenantId) {
        return res.status(400).json({
          error: 'Tenant context required',
          code: 'TENANT_CONTEXT_REQUIRED'
        });
      }

      // Modify request to include tenant filtering
      if (req.query && typeof req.query === 'object') {
        req.query = {
          ...req.query,
          where: {
            ...req.query.where,
            tenantId: req.tenantId
          }
        };
      }

      // Add tenant filter to request for use in controllers
      req.tenantFilter = { tenantId: req.tenantId };
      
      next();
    };
  }

  /**
   * Validate tenant ownership of resources
   */
  validateTenantOwnership(resourceType) {
    return async (req, res, next) => {
      try {
        if (!req.user || !req.tenantId) {
          return res.status(401).json({
            error: 'Authentication and tenant context required',
            code: 'AUTH_TENANT_REQUIRED'
          });
        }

        const resourceId = req.params.id || req.body.id;
        if (!resourceId) {
          return next(); // Skip if no resource ID (create operations)
        }

        // Admin can access any resource
        if (req.user.role?.name === 'admin') {
          return next();
        }

        let resource;
        switch (resourceType) {
          case 'candidate':
            resource = await this.tenantService.db.candidates.findByPk(resourceId);
            break;
          case 'application':
            resource = await this.tenantService.db.applications.findByPk(resourceId);
            break;
          case 'user':
            resource = await this.tenantService.db.users.findByPk(resourceId);
            break;
          default:
            return res.status(400).json({
              error: 'Invalid resource type',
              code: 'INVALID_RESOURCE_TYPE'
            });
        }

        if (!resource) {
          return res.status(404).json({
            error: 'Resource not found',
            code: 'RESOURCE_NOT_FOUND'
          });
        }

        if (resource.tenantId !== req.tenantId) {
          await this.logSecurityEvent('CROSS_TENANT_RESOURCE_ACCESS', req.user.id, {
            userTenantId: req.tenantId,
            resourceTenantId: resource.tenantId,
            resourceType,
            resourceId,
            path: req.path,
            method: req.method,
            ipAddress: req.ip
          });

          return res.status(403).json({
            error: 'Resource access denied: Wrong tenant',
            code: 'CROSS_TENANT_RESOURCE_ACCESS',
            userTenantId: req.tenantId,
            resourceTenantId: resource.tenantId
          });
        }

        next();
      } catch (error) {
        console.error('Tenant ownership validation failed:', error);
        return res.status(500).json({
          error: 'Resource ownership validation failed',
          code: 'OWNERSHIP_VALIDATION_ERROR'
        });
      }
    };
  }

  /**
   * Add tenant information to response headers
   */
  addTenantHeaders() {
    return (req, res, next) => {
      if (req.tenantId) {
        res.set({
          'X-Tenant-ID': req.tenantId,
          'X-Tenant-Context': 'active'
        });
      }
      next();
    };
  }

  /**
   * Cleanup tenant context after request
   */
  cleanupTenantContext() {
    return async (req, res, next) => {
      // This will be called after the response is sent
      res.on('finish', async () => {
        try {
          await this.tenantService.clearTenantContext();
        } catch (error) {
          console.error('Failed to cleanup tenant context:', error);
        }
      });
      next();
    };
  }

  /**
   * Log security events for tenant violations
   */
  async logSecurityEvent(eventType, userId, metadata) {
    try {
      await this.tenantService.db.securityLogs.create({
        id: require('uuid').v4(),
        eventType,
        userId,
        metadata: JSON.stringify(metadata),
        ipAddress: metadata.ipAddress,
        userAgent: metadata.userAgent,
        timestamp: new Date(),
        severity: 'HIGH'
      });
    } catch (error) {
      console.error('Failed to log security event:', error);
    }
  }

  /**
   * Middleware to validate tenant plan features
   */
  validateTenantFeature(feature) {
    return async (req, res, next) => {
      try {
        if (!req.user || !req.tenantId) {
          return next(); // Skip if no tenant context
        }

        // Admin bypasses feature limits
        if (req.user.role?.name === 'admin') {
          return next();
        }

        const tenant = await this.tenantService.db.tenants.findByPk(req.tenantId, {
          include: [{
            model: this.tenantService.db.tenantSettings,
            as: 'settings'
          }]
        });

        if (!tenant || !tenant.settings) {
          return res.status(500).json({
            error: 'Tenant settings not found',
            code: 'TENANT_SETTINGS_MISSING'
          });
        }

        const settings = JSON.parse(tenant.settings.features || '{}');
        
        if (!settings[feature]) {
          return res.status(403).json({
            error: 'Feature not available in your plan',
            code: 'FEATURE_NOT_AVAILABLE',
            feature,
            plan: tenant.plan,
            message: `The '${feature}' feature is not available in your ${tenant.plan} plan. Please upgrade to access this feature.`
          });
        }

        next();
      } catch (error) {
        console.error('Feature validation failed:', error);
        return res.status(500).json({
          error: 'Feature validation failed',
          code: 'FEATURE_VALIDATION_ERROR'
        });
      }
    };
  }

  /**
   * Add tenant-specific rate limiting
   */
  tenantRateLimit(options = {}) {
    const {
      windowMs = 15 * 60 * 1000, // 15 minutes
      basic = { max: 100 },
      professional = { max: 500 },
      enterprise = { max: 2000 },
      admin = { max: 5000 }
    } = options;

    const attempts = new Map();

    return async (req, res, next) => {
      try {
        if (!req.user || !req.tenantId) {
          return next();
        }

        // Get tenant plan
        const tenant = await this.tenantService.db.tenants.findByPk(req.tenantId);
        const plan = tenant?.plan || 'basic';
        
        // Admin bypasses rate limits
        if (req.user.role?.name === 'admin') {
          return next();
        }

        const config = options[plan] || basic;
        const key = `${req.tenantId}:${req.path}`;
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
        
        if (current.count >= config.max && current.lastAttempt > windowStart) {
          return res.status(429).json({
            error: 'Tenant rate limit exceeded',
            code: 'TENANT_RATE_LIMIT_EXCEEDED',
            retryAfter: Math.ceil((current.lastAttempt + windowMs - now) / 1000),
            limit: config.max,
            plan,
            windowMs
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
          'X-RateLimit-Reset': new Date(now + windowMs),
          'X-Tenant-Plan': plan
        });

        next();
      } catch (error) {
        console.error('Tenant rate limiting failed:', error);
        next(); // Don't block the request if rate limiting fails
      }
    };
  }

  /**
   * Validate tenant data access patterns
   */
  validateDataAccess() {
    return (req, res, next) => {
      try {
        // Check for potential cross-tenant data access in query parameters
        const suspiciousParams = ['tenantId', 'tenant_id', 'organizationId'];
        const foundSuspiciousParam = suspiciousParams.find(param => 
          req.query[param] && req.query[param] !== req.tenantId
        );

        if (foundSuspiciousParam && req.user.role?.name !== 'admin') {
          return res.status(400).json({
            error: 'Invalid query parameter',
            code: 'SUSPICIOUS_QUERY_PARAM',
            parameter: foundSuspiciousParam
          });
        }

        // Validate that filter objects don't contain tenant filters
        if (req.body && req.body.filter && typeof req.body.filter === 'object') {
          const filterKeys = Object.keys(req.body.filter);
          const tenantFilterKeys = filterKeys.filter(key => 
            key.toLowerCase().includes('tenant')
          );

          if (tenantFilterKeys.length > 0 && req.user.role?.name !== 'admin') {
            return res.status(400).json({
              error: 'Tenant filters not allowed in request body',
              code: 'TENANT_FILTER_NOT_ALLOWED',
              filters: tenantFilterKeys
            });
          }
        }

        next();
      } catch (error) {
        console.error('Data access validation failed:', error);
        next();
      }
    };
  }
}

module.exports = TenantMiddleware;
