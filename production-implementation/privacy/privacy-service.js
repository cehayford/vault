/**
 * Privacy and Data Protection Service
 * Handles GDPR compliance, data encryption, PII masking, and privacy controls
 */

const crypto = require('crypto');
const bcrypt = require('bcryptjs');

class PrivacyService {
  constructor(database, config) {
    this.db = database;
    this.config = config;
    this.encryptionKey = config.ENCRYPTION_KEY || crypto.randomBytes(32);
    this.algorithm = 'aes-256-gcm';
    this.dataRetentionDays = config.DATA_RETENTION_DAYS || 2555; // 7 years default
  }

  /**
   * Encrypt sensitive data
   */
  encrypt(text) {
    try {
      const iv = crypto.randomBytes(16);
      const cipher = crypto.createCipher(this.algorithm, this.encryptionKey);
      cipher.setAAD(Buffer.from('engineering-orchestration', 'utf8'));
      
      let encrypted = cipher.update(text, 'utf8', 'hex');
      encrypted += cipher.final('hex');
      
      const authTag = cipher.getAuthTag();
      
      return {
        encrypted,
        iv: iv.toString('hex'),
        authTag: authTag.toString('hex')
      };
    } catch (error) {
      throw new Error(`Encryption failed: ${error.message}`);
    }
  }

  /**
   * Decrypt sensitive data
   */
  decrypt(encryptedData) {
    try {
      const { encrypted, iv, authTag } = encryptedData;
      const decipher = crypto.createDecipher(this.algorithm, this.encryptionKey);
      decipher.setAAD(Buffer.from('engineering-orchestration', 'utf8'));
      decipher.setAuthTag(Buffer.from(authTag, 'hex'));
      
      let decrypted = decipher.update(encrypted, 'hex', 'utf8');
      decrypted += decipher.final('utf8');
      
      return decrypted;
    } catch (error) {
      throw new Error(`Decryption failed: ${error.message}`);
    }
  }

  /**
   * Mask PII data for non-privileged users
   */
  maskPII(data, userRole, resourceOwnership = 'own') {
    const maskedData = { ...data };
    
    // Define PII fields that need masking
    const piiFields = [
      'email', 'phoneNumber', 'ssn', 'address', 'dateOfBirth',
      'firstName', 'lastName', 'fullName', 'nationalId', 'passportNumber'
    ];

    // Define masking rules based on role and ownership
    const shouldMask = (field) => {
      // Admins can see all data
      if (userRole === 'admin') return false;
      
      // Users can see their own full data
      if (resourceOwnership === 'own') return false;
      
      // Creators can see partial data of others in their tenant
      if (userRole === 'creator' && resourceOwnership === 'tenant') {
        return this.shouldPartialMask(field);
      }
      
      // Viewers get heavily masked data
      return true;
    };

    // Apply masking
    piiFields.forEach(field => {
      if (maskedData[field] && shouldMask(field)) {
        maskedData[field] = this.maskField(field, maskedData[field]);
      }
    });

    return maskedData;
  }

  /**
   * Determine if field should be partially masked
   */
  shouldPartialMask(field) {
    const partialMaskFields = ['firstName', 'lastName', 'email'];
    return partialMaskFields.includes(field);
  }

  /**
   * Apply specific masking to a field
   */
  maskField(field, value) {
    if (!value) return value;

    switch (field) {
      case 'email':
        const [username, domain] = value.split('@');
        return `${username.slice(0, 2)}***@${domain}`;
      
      case 'phoneNumber':
        return value.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2');
      
      case 'ssn':
      case 'nationalId':
        return value.slice(0, 3) + '***' + value.slice(-2);
      
      case 'firstName':
      case 'lastName':
        return value.slice(0, 1) + '***';
      
      case 'address':
        return '*** CONFIDENTIAL ***';
      
      case 'dateOfBirth':
        return '**/**/****';
      
      default:
        return '***';
    }
  }

  /**
   * Hash sensitive identifiers for comparison
   */
  hashIdentifier(identifier) {
    return crypto.createHash('sha256').update(identifier).digest('hex');
  }

  /**
   * Check if data contains PII
   */
  containsPII(data) {
    const piiPatterns = [
      /\b\d{3}-\d{2}-\d{4}\b/, // SSN pattern
      /\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b/, // Credit card pattern
      /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/, // Email pattern
      /\b\d{3}[-.]?\d{3}[-.]?\d{4}\b/, // Phone pattern
    ];

    const dataString = JSON.stringify(data);
    return piiPatterns.some(pattern => pattern.test(dataString));
  }

  /**
   * Log data access for audit purposes
   */
  async logDataAccess(userId, resourceType, resourceId, action, metadata = {}) {
    try {
      await this.db.privacyLogs.create({
        id: crypto.randomUUID(),
        userId,
        resourceType,
        resourceId,
        action,
        metadata: JSON.stringify(metadata),
        ipAddress: metadata.ipAddress,
        userAgent: metadata.userAgent,
        timestamp: new Date()
      });
    } catch (error) {
      console.error('Failed to log data access:', error);
    }
  }

  /**
   * Handle data subject access request (DSAR)
   */
  async handleDataSubjectRequest(userId, requestType, requestId) {
    try {
      const user = await this.db.users.findByPk(userId);
      if (!user) {
        throw new Error('User not found');
      }

      let requestData = {};

      switch (requestType) {
        case 'access':
          requestData = await this.getAllUserData(userId);
          break;
        case 'portability':
          requestData = await this.getPortableUserData(userId);
          break;
        case 'deletion':
          requestData = await this.initiateDataDeletion(userId);
          break;
        case 'rectification':
          requestData = await this.prepareDataRectification(userId);
          break;
        default:
          throw new Error('Invalid request type');
      }

      // Update request status
      await this.db.dataSubjectRequests.update({
        status: 'processing',
        processedAt: new Date(),
        metadata: JSON.stringify(requestData)
      }, {
        where: { id: requestId }
      });

      return requestData;
    } catch (error) {
      throw new Error(`DSAR handling failed: ${error.message}`);
    }
  }

  /**
   * Get all user data for access requests
   */
  async getAllUserData(userId) {
    try {
      const user = await this.db.users.findByPk(userId, {
        attributes: { exclude: ['passwordHash', 'resetToken'] },
        include: [
          {
            model: this.db.candidates,
            as: 'candidates',
            include: [
              { model: this.db.applications, as: 'applications' },
              { model: this.db.notes, as: 'notes' }
            ]
          },
          {
            model: this.db.documents,
            as: 'documents'
          }
        ]
      });

      // Remove sensitive data that shouldn't be exported
      return this.sanitizeForExport(user);
    } catch (error) {
      throw new Error(`Failed to retrieve user data: ${error.message}`);
    }
  }

  /**
   * Get user data in portable format
   */
  async getPortableUserData(userId) {
    try {
      const userData = await this.getAllUserData(userId);
      
      return {
        format: 'json',
        version: '1.0',
        exportedAt: new Date().toISOString(),
        data: userData,
        schema: {
          user: 'Personal profile information',
          candidates: 'Candidate records created by user',
          applications: 'Application records',
          notes: 'Notes and comments',
          documents: 'Uploaded documents metadata'
        }
      };
    } catch (error) {
      throw new Error(`Failed to create portable data: ${error.message}`);
    }
  }

  /**
   * Initiate data deletion (right to be forgotten)
   */
  async initiateDataDeletion(userId) {
    try {
      // Create deletion request
      const deletionRequest = await this.db.dataDeletionRequests.create({
        id: crypto.randomUUID(),
        userId,
        status: 'pending',
        requestedAt: new Date(),
        scheduledFor: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days
        metadata: JSON.stringify({ reason: 'GDPR Right to be Forgotten' })
      });

      // Schedule deletion job
      this.scheduleDataDeletion(userId, deletionRequest.id);

      return {
        requestId: deletionRequest.id,
        scheduledFor: deletionRequest.scheduledFor,
        message: 'Data deletion scheduled. You have 30 days to cancel this request.'
      };
    } catch (error) {
      throw new Error(`Failed to initiate data deletion: ${error.message}`);
    }
  }

  /**
   * Schedule data deletion job
   */
  scheduleDataDeletion(userId, requestId) {
    // This would integrate with your job scheduler (e.g., Bull, Agenda)
    setTimeout(async () => {
      try {
        await this.executeDataDeletion(userId, requestId);
      } catch (error) {
        console.error('Scheduled data deletion failed:', error);
      }
    }, 30 * 24 * 60 * 60 * 1000); // 30 days
  }

  /**
   * Execute actual data deletion
   */
  async executeDataDeletion(userId, requestId) {
    try {
      const transaction = await this.db.sequelize.transaction();

      try {
        // Delete user-generated data
        await this.db.candidates.destroy({ 
          where: { createdBy: userId }, 
          transaction 
        });
        
        await this.db.applications.destroy({ 
          where: { createdBy: userId }, 
          transaction 
        });
        
        await this.db.notes.destroy({ 
          where: { createdBy: userId }, 
          transaction 
        });
        
        await this.db.documents.destroy({ 
          where: { uploadedBy: userId }, 
          transaction 
        });

        // Anonymize user record instead of deleting (for audit purposes)
        await this.db.users.update({
          email: `deleted-${userId}@deleted.com`,
          firstName: 'Deleted',
          lastName: 'User',
          phoneNumber: null,
          isActive: false,
          deletedAt: new Date(),
          passwordHash: null,
          resetToken: null
        }, {
          where: { id: userId },
          transaction
        });

        // Update deletion request status
        await this.db.dataDeletionRequests.update({
          status: 'completed',
          completedAt: new Date()
        }, {
          where: { id: requestId },
          transaction
        });

        await transaction.commit();

        // Log deletion
        await this.logPrivacyEvent('DATA_DELETED', userId, {
          requestId,
          timestamp: new Date()
        });

      } catch (error) {
        await transaction.rollback();
        throw error;
      }
    } catch (error) {
      throw new Error(`Data deletion execution failed: ${error.message}`);
    }
  }

  /**
   * Prepare data for rectification
   */
  async prepareDataRectification(userId) {
    try {
      const userData = await this.getAllUserData(userId);
      
      return {
        currentData: userData,
        rectifiableFields: [
          'firstName', 'lastName', 'email', 'phoneNumber',
          'address', 'dateOfBirth'
        ],
        instructions: 'Submit updated values for the fields you wish to rectify'
      };
    } catch (error) {
      throw new Error(`Failed to prepare data rectification: ${error.message}`);
    }
  }

  /**
   * Apply data retention policies
   */
  async applyDataRetention() {
    try {
      const cutoffDate = new Date();
      cutoffDate.setDate(cutoffDate.getDate() - this.dataRetentionDays);

      // Archive old inactive user data
      const archivedUsers = await this.db.users.update({
        isActive: false,
        archivedAt: new Date()
      }, {
        where: {
          lastLoginAt: { [this.db.Sequelize.Op.lt]: cutoffDate },
          isActive: true
        }
      });

      // Archive old candidates
      const archivedCandidates = await this.db.candidates.update({
        status: 'archived'
      }, {
        where: {
          createdAt: { [this.db.Sequelize.Op.lt]: cutoffDate },
          status: { [this.db.Sequelize.Op.ne]: 'archived' }
        }
      });

      return {
        archivedUsers: archivedUsers[0],
        archivedCandidates: archivedCandidates[0],
        cutoffDate
      };
    } catch (error) {
      throw new Error(`Data retention application failed: ${error.message}`);
    }
  }

  /**
   * Generate consent management tokens
   */
  generateConsentToken(userId, consentType) {
    const payload = {
      userId,
      consentType,
      timestamp: Date.now(),
      nonce: crypto.randomBytes(16).toString('hex')
    };

    return crypto.createHmac('sha256', this.encryptionKey)
      .update(JSON.stringify(payload))
      .digest('hex');
  }

  /**
   * Handle consent withdrawal
   */
  async withdrawConsent(userId, consentType, reason) {
    try {
      await this.db.consents.update({
        status: 'withdrawn',
        withdrawnAt: new Date(),
        withdrawalReason: reason
      }, {
        where: {
          userId,
          consentType,
          status: 'active'
        }
      });

      // Log consent withdrawal
      await this.logPrivacyEvent('CONSENT_WITHDRAWN', userId, {
        consentType,
        reason,
        timestamp: new Date()
      });

      // Apply data processing restrictions based on consent type
      await this.applyConsentRestrictions(userId, consentType);

      return { success: true, message: 'Consent withdrawn successfully' };
    } catch (error) {
      throw new Error(`Consent withdrawal failed: ${error.message}`);
    }
  }

  /**
   * Apply processing restrictions based on consent
   */
  async applyConsentRestrictions(userId, consentType) {
    try {
      switch (consentType) {
        case 'marketing':
          // Remove from marketing lists
          await this.db.users.update({
            marketingConsent: false
          }, { where: { id: userId } });
          break;
        
        case 'analytics':
          // Disable analytics tracking
          await this.db.users.update({
            analyticsConsent: false
          }, { where: { id: userId } });
          break;
        
        case 'profiling':
          // Disable automated profiling
          await this.db.users.update({
            profilingConsent: false
          }, { where: { id: userId } });
          break;
      }
    } catch (error) {
      console.error('Failed to apply consent restrictions:', error);
    }
  }

  /**
   * Sanitize data for export
   */
  sanitizeForExport(data) {
    const sanitized = JSON.parse(JSON.stringify(data));
    
    // Remove system fields
    delete sanitized.passwordHash;
    delete sanitized.resetToken;
    delete sanitized.loginAttempts;
    delete sanitized.lockUntil;
    
    // Remove sensitive audit data
    if (sanitized.auditLogs) {
      sanitized.auditLogs = sanitized.auditLogs.map(log => ({
        action: log.action,
        timestamp: log.timestamp
      }));
    }

    return sanitized;
  }

  /**
   * Log privacy events
   */
  async logPrivacyEvent(eventType, userId, metadata = {}) {
    try {
      await this.db.privacyLogs.create({
        id: crypto.randomUUID(),
        eventType,
        userId,
        metadata: JSON.stringify(metadata),
        timestamp: new Date(),
        severity: this.getEventSeverity(eventType)
      });
    } catch (error) {
      console.error('Failed to log privacy event:', error);
    }
  }

  /**
   * Get event severity level
   */
  getEventSeverity(eventType) {
    const severityMap = {
      'DATA_ACCESSED': 'LOW',
      'DATA_EXPORTED': 'MEDIUM',
      'CONSENT_WITHDRAWN': 'MEDIUM',
      'DATA_DELETED': 'HIGH',
      'DATA_BREACH': 'CRITICAL'
    };
    
    return severityMap[eventType] || 'MEDIUM';
  }

  /**
   * Generate privacy report
   */
  async generatePrivacyReport(userId, startDate, endDate) {
    try {
      const privacyLogs = await this.db.privacyLogs.findAll({
        where: {
          userId,
          timestamp: {
            [this.db.Sequelize.Op.between]: [startDate, endDate]
          }
        },
        order: [['timestamp', 'DESC']]
      });

      const consents = await this.db.consents.findAll({
        where: { userId },
        order: [['createdAt', 'DESC']]
      });

      const dataAccess = await this.db.privacyLogs.findAll({
        where: {
          userId,
          eventType: 'DATA_ACCESSED',
          timestamp: {
            [this.db.Sequelize.Op.between]: [startDate, endDate]
          }
        }
      });

      return {
        userId,
        reportPeriod: { startDate, endDate },
        summary: {
          totalAccessEvents: dataAccess.length,
          consentChanges: consents.filter(c => c.status !== 'active').length,
          dataExports: privacyLogs.filter(l => l.eventType === 'DATA_EXPORTED').length
        },
        details: {
          accessLog: dataAccess,
          consentStatus: consents,
          privacyEvents: privacyLogs
        },
        generatedAt: new Date()
      };
    } catch (error) {
      throw new Error(`Privacy report generation failed: ${error.message}`);
    }
  }
}

module.exports = PrivacyService;
