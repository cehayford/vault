/**
 * Multi-Tenancy Service
 * Manages tenant isolation, data segregation, and cross-tenant access prevention
 */

class TenantService {
  constructor(database) {
    this.db = database;
  }

  /**
   * Create a new tenant with initial setup
   */
  async createTenant(tenantData, creatorId) {
    try {
      const { name, plan = 'basic', settings = {} } = tenantData;
      const { v4: uuidv4 } = require('uuid');

      // Create tenant
      const tenant = await this.db.tenants.create({
        id: uuidv4(),
        name,
        plan,
        settings: JSON.stringify(settings),
        isActive: true,
        createdBy: creatorId,
        createdAt: new Date(),
        updatedAt: new Date()
      });

      // Initialize tenant-specific configurations
      await this.initializeTenantSettings(tenant.id);

      // Log tenant creation
      await this.db.auditLogs.create({
        userId: creatorId,
        action: 'TENANT_CREATED',
        targetType: 'tenant',
        targetId: tenant.id,
        newValues: JSON.stringify({ name, plan }),
        timestamp: new Date()
      });

      return tenant;
    } catch (error) {
      throw new Error(`Failed to create tenant: ${error.message}`);
    }
  }

  /**
   * Initialize tenant-specific settings and configurations
   */
  async initializeTenantSettings(tenantId) {
    try {
      // Create default tenant settings
      await this.db.tenantSettings.create({
        id: require('uuid').v4(),
        tenantId,
        maxUsers: this.getDefaultUserLimit('basic'),
        maxCandidates: 1000,
        maxApplications: 5000,
        storageQuota: 1024 * 1024 * 1024, // 1GB
        features: JSON.stringify({
          advanced_search: false,
          custom_fields: false,
          api_access: false,
          sso_integration: false
        }),
        createdAt: new Date(),
        updatedAt: new Date()
      });

      // Create default tenant permissions
      await this.createDefaultTenantPermissions(tenantId);

    } catch (error) {
      throw new Error(`Failed to initialize tenant settings: ${error.message}`);
    }
  }

  /**
   * Get default user limit based on plan
   */
  getDefaultUserLimit(plan) {
    const limits = {
      basic: 5,
      professional: 25,
      enterprise: 100,
      custom: 1000
    };
    return limits[plan] || limits.basic;
  }

  /**
   * Create default permissions for tenant
   */
  async createDefaultTenantPermissions(tenantId) {
    const defaultPermissions = [
      { resource: 'candidates', actions: ['create', 'read:own', 'update:own', 'delete:own'] },
      { resource: 'applications', actions: ['create', 'read:own', 'update:own', 'delete:own'] },
      { resource: 'users', actions: ['read:own'] },
      { resource: 'profile', actions: ['read', 'update'] }
    ];

    for (const permission of defaultPermissions) {
      for (const action of permission.actions) {
        await this.db.tenantPermissions.create({
          id: require('uuid').v4(),
          tenantId,
          resource: permission.resource,
          action,
          isDefault: true,
          createdAt: new Date()
        });
      }
    }
  }

  /**
   * Add tenant_id column to existing tables (migration)
   */
  async migrateToMultiTenant() {
    try {
      const queryInterface = this.db.getQueryInterface();

      // List of tables that need tenant isolation
      const tablesToMigrate = [
        'candidates',
        'applications',
        'interviews',
        'notes',
        'documents',
        'tags',
        'workflows'
      ];

      for (const tableName of tablesToMigrate) {
        // Check if table exists
        const tableExists = await queryInterface.tableExists(tableName);
        if (!tableExists) continue;

        // Check if tenant_id column already exists
        const tableDescription = await queryInterface.describeTable(tableName);
        if (!tableDescription.tenantId) {
          // Add tenant_id column
          await queryInterface.addColumn(tableName, 'tenantId', {
            type: this.db.Sequelize.UUID,
            allowNull: false,
            defaultValue: null
          });

          // Add foreign key constraint
          await queryInterface.addConstraint(tableName, {
            fields: ['tenantId'],
            type: 'foreign key',
            name: `fk_${tableName}_tenantId`,
            references: {
              table: 'tenants',
              field: 'id'
            },
            onDelete: 'CASCADE',
            onUpdate: 'CASCADE'
          });

          // Add index for performance
          await queryInterface.addIndex(tableName, ['tenantId']);

          console.log(`Added tenant isolation to ${tableName}`);
        }
      }

      // Create Row Level Security (RLS) policies for PostgreSQL
      if (this.db.getDialect() === 'postgres') {
        await this.createRLSPolicies();
      }

      return { success: true, message: 'Multi-tenancy migration completed' };
    } catch (error) {
      throw new Error(`Migration failed: ${error.message}`);
    }
  }

  /**
   * Create Row Level Security policies for PostgreSQL
   */
  async createRLSPolicies() {
    const policies = [
      {
        table: 'candidates',
        policy: 'tenant_isolation_policy',
        definition: `
          CREATE POLICY tenant_isolation_policy ON candidates
          FOR ALL TO authenticated_users
          USING (tenantId = current_setting('app.current_tenant_id')::UUID);
        `
      },
      {
        table: 'applications',
        policy: 'tenant_isolation_policy',
        definition: `
          CREATE POLICY tenant_isolation_policy ON applications
          FOR ALL TO authenticated_users
          USING (tenantId = current_setting('app.current_tenant_id')::UUID);
        `
      }
    ];

    for (const { table, policy, definition } of policies) {
      try {
        // Enable RLS on table
        await this.db.query(`ALTER TABLE ${table} ENABLE ROW LEVEL SECURITY;`);
        
        // Drop existing policy if it exists
        await this.db.query(`DROP POLICY IF EXISTS ${policy} ON ${table};`);
        
        // Create new policy
        await this.db.query(definition);
        
        console.log(`Created RLS policy for ${table}`);
      } catch (error) {
        console.warn(`Failed to create RLS policy for ${table}:`, error.message);
      }
    }
  }

  /**
   * Set tenant context for database session
   */
  async setTenantContext(tenantId) {
    try {
      if (this.db.getDialect() === 'postgres') {
        await this.db.query(`SET app.current_tenant_id = '${tenantId}';`);
      }
      return true;
    } catch (error) {
      console.error('Failed to set tenant context:', error);
      return false;
    }
  }

  /**
   * Clear tenant context
   */
  async clearTenantContext() {
    try {
      if (this.db.getDialect() === 'postgres') {
        await this.db.query(`RESET app.current_tenant_id;`);
      }
      return true;
    } catch (error) {
      console.error('Failed to clear tenant context:', error);
      return false;
    }
  }

  /**
   * Verify data isolation between tenants
   */
  async verifyDataIsolation() {
    try {
      const results = {};

      // Get all tenants
      const tenants = await this.db.tenants.findAll({
        attributes: ['id', 'name']
      });

      for (const tenant of tenants) {
        // Count resources per tenant
        const candidateCount = await this.db.candidates.count({
          where: { tenantId: tenant.id }
        });
        
        const applicationCount = await this.db.applications.count({
          where: { tenantId: tenant.id }
        });

        results[tenant.name] = {
          tenantId: tenant.id,
          candidates: candidateCount,
          applications: applicationCount
        };
      }

      // Check for any data without tenant association
      const orphanedCandidates = await this.db.candidates.count({
        where: { tenantId: null }
      });

      const orphanedApplications = await this.db.applications.count({
        where: { tenantId: null }
      });

      return {
        tenantData: results,
        orphanedData: {
          candidates: orphanedCandidates,
          applications: orphanedApplications
        },
        isIsolated: orphanedCandidates === 0 && orphanedApplications === 0
      };
    } catch (error) {
      throw new Error(`Data isolation verification failed: ${error.message}`);
    }
  }

  /**
   * Assign existing data to correct tenant (migration helper)
   */
  async assignDataToTenant(userId, tenantId) {
    try {
      // Update all user-created data to belong to their tenant
      const [candidatesUpdated] = await this.db.candidates.update(
        { tenantId },
        { where: { createdBy: userId } }
      );

      const [applicationsUpdated] = await this.db.applications.update(
        { tenantId },
        { where: { createdBy: userId } }
      );

      // Log the migration
      await this.db.auditLogs.create({
        userId,
        action: 'DATA_MIGRATED_TO_TENANT',
        targetType: 'tenant',
        targetId: tenantId,
        newValues: JSON.stringify({
          candidatesUpdated,
          applicationsUpdated
        }),
        timestamp: new Date()
      });

      return {
        candidatesUpdated,
        applicationsUpdated
      };
    } catch (error) {
      throw new Error(`Failed to assign data to tenant: ${error.message}`);
    }
  }

  /**
   * Get tenant statistics
   */
  async getTenantStats(tenantId) {
    try {
      const stats = await this.db.tenants.findByPk(tenantId, {
        attributes: ['id', 'name', 'plan', 'createdAt'],
        include: [
          {
            model: this.db.users,
            as: 'users',
            attributes: ['id', 'email', 'role', 'isActive', 'createdAt'],
            required: false
          },
          {
            model: this.db.tenantSettings,
            as: 'settings',
            required: false
          }
        ]
      });

      if (!stats) {
        throw new Error('Tenant not found');
      }

      // Count resources
      const candidateCount = await this.db.candidates.count({
        where: { tenantId }
      });

      const applicationCount = await this.db.applications.count({
        where: { tenantId }
      });

      const activeUserCount = await this.db.users.count({
        where: { 
          tenantId,
          isActive: true 
        }
      });

      return {
        tenant: stats,
        statistics: {
          candidates: candidateCount,
          applications: applicationCount,
          activeUsers: activeUserCount,
          totalUsers: stats.users?.length || 0
        }
      };
    } catch (error) {
      throw new Error(`Failed to get tenant stats: ${error.message}`);
    }
  }

  /**
   * Update tenant settings
   */
  async updateTenantSettings(tenantId, settings, updatedBy) {
    try {
      const tenant = await this.db.tenants.findByPk(tenantId);
      if (!tenant) {
        throw new Error('Tenant not found');
      }

      const oldSettings = tenant.settings;

      await this.db.tenants.update({
        settings: JSON.stringify(settings),
        updatedAt: new Date()
      }, { where: { id: tenantId } });

      // Log settings update
      await this.db.auditLogs.create({
        userId: updatedBy,
        action: 'TENANT_SETTINGS_UPDATED',
        targetType: 'tenant',
        targetId: tenantId,
        oldValues: oldSettings,
        newValues: JSON.stringify(settings),
        timestamp: new Date()
      });

      return await this.db.tenants.findByPk(tenantId);
    } catch (error) {
      throw new Error(`Failed to update tenant settings: ${error.message}`);
    }
  }

  /**
   * Check if tenant has reached resource limits
   */
  async checkTenantLimits(tenantId) {
    try {
      const settings = await this.db.tenantSettings.findOne({
        where: { tenantId }
      });

      if (!settings) {
        throw new Error('Tenant settings not found');
      }

      const currentStats = await this.getTenantStats(tenantId);

      const limits = {
        users: {
          current: currentStats.statistics.activeUsers,
          max: settings.maxUsers,
          exceeded: currentStats.statistics.activeUsers >= settings.maxUsers
        },
        candidates: {
          current: currentStats.statistics.candidates,
          max: settings.maxCandidates,
          exceeded: currentStats.statistics.candidates >= settings.maxCandidates
        },
        applications: {
          current: currentStats.statistics.applications,
          max: settings.maxApplications,
          exceeded: currentStats.statistics.applications >= settings.maxApplications
        }
      };

      return {
        limits,
        anyExceeded: Object.values(limits).some(limit => limit.exceeded)
      };
    } catch (error) {
      throw new Error(`Failed to check tenant limits: ${error.message}`);
    }
  }

  /**
   * Archive tenant data (soft delete)
   */
  async archiveTenant(tenantId, archivedBy) {
    try {
      const tenant = await this.db.tenants.findByPk(tenantId);
      if (!tenant) {
        throw new Error('Tenant not found');
      }

      // Soft delete tenant
      await this.db.tenants.update({
        isActive: false,
        archivedAt: new Date(),
        archivedBy,
        updatedAt: new Date()
      }, { where: { id: tenantId } });

      // Deactivate all users in tenant
      await this.db.users.update({
        isActive: false,
        updatedAt: new Date()
      }, { where: { tenantId } });

      // Log archiving
      await this.db.auditLogs.create({
        userId: archivedBy,
        action: 'TENANT_ARCHIVED',
        targetType: 'tenant',
        targetId: tenantId,
        oldValues: JSON.stringify({ name: tenant.name, isActive: true }),
        newValues: JSON.stringify({ isActive: false, archivedAt: new Date() }),
        timestamp: new Date()
      });

      return { success: true, message: 'Tenant archived successfully' };
    } catch (error) {
      throw new Error(`Failed to archive tenant: ${error.message}`);
    }
  }

  /**
   * Delete tenant and all associated data (hard delete)
   */
  async deleteTenant(tenantId, deletedBy) {
    try {
      const tenant = await this.db.tenants.findByPk(tenantId);
      if (!tenant) {
        throw new Error('Tenant not found');
      }

      // This will cascade delete all related data due to foreign key constraints
      await this.db.tenants.destroy({
        where: { id: tenantId }
      });

      // Log deletion
      await this.db.auditLogs.create({
        userId: deletedBy,
        action: 'TENANT_DELETED',
        targetType: 'tenant',
        targetId: tenantId,
        oldValues: JSON.stringify({ name: tenant.name }),
        timestamp: new Date()
      });

      return { success: true, message: 'Tenant deleted permanently' };
    } catch (error) {
      throw new Error(`Failed to delete tenant: ${error.message}`);
    }
  }
}

module.exports = TenantService;
