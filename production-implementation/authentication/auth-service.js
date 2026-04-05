/**
 * Authentication Service - Production Implementation
 * Handles user authentication, JWT tokens, and session management
 */

const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const crypto = require('crypto');
const { v4: uuidv4 } = require('uuid');

class AuthService {
  constructor(database, config) {
    this.db = database;
    this.config = config;
    this.jwtSecret = config.JWT_SECRET;
    this.jwtExpiry = config.JWT_EXPIRY || '24h';
    this.refreshTokenExpiry = config.REFRESH_TOKEN_EXPIRY || '7d';
    this.maxLoginAttempts = config.MAX_LOGIN_ATTEMPTS || 5;
    this.lockoutTime = config.LOCKOUT_TIME || 15 * 60 * 1000; // 15 minutes
  }

  /**
   * Register a new user
   */
  async register(userData) {
    const { email, password, firstName, lastName, role = 'creator' } = userData;
    
    // Validate input
    this.validateEmail(email);
    this.validatePassword(password);
    
    // Check if user already exists
    const existingUser = await this.db.users.findOne({ where: { email } });
    if (existingUser) {
      throw new Error('User with this email already exists');
    }

    // Hash password
    const saltRounds = 12;
    const passwordHash = await bcrypt.hash(password, saltRounds);

    // Create user with tenant
    const tenantId = uuidv4();
    const user = await this.db.users.create({
      id: uuidv4(),
      email: email.toLowerCase(),
      passwordHash,
      firstName,
      lastName,
      role,
      tenantId,
      isActive: true,
      emailVerified: false,
      loginAttempts: 0,
      lockUntil: null,
      createdAt: new Date(),
      updatedAt: new Date()
    });

    // Create tenant record
    await this.db.tenants.create({
      id: tenantId,
      name: `${firstName} ${lastName}'s Organization`,
      plan: 'basic',
      isActive: true,
      createdAt: new Date(),
      updatedAt: new Date()
    });

    // Generate tokens
    const tokens = await this.generateTokens(user);
    
    // Log registration
    await this.logAuthEvent('USER_REGISTERED', user.id, {
      email: user.email,
      role: user.role,
      tenantId: user.tenantId
    });

    return {
      user: this.sanitizeUser(user),
      tokens
    };
  }

  /**
   * Authenticate user and generate tokens
   */
  async login(email, password, ipAddress, userAgent) {
    // Find user
    const user = await this.db.users.findOne({ where: { email: email.toLowerCase() } });
    if (!user) {
      await this.logAuthEvent('LOGIN_FAILED', null, { email, reason: 'USER_NOT_FOUND' });
      throw new Error('Invalid credentials');
    }

    // Check if account is locked
    if (user.lockUntil && user.lockUntil > Date.now()) {
      const lockTimeRemaining = Math.ceil((user.lockUntil - Date.now()) / 60000);
      throw new Error(`Account locked. Try again in ${lockTimeRemaining} minutes`);
    }

    // Check if account is active
    if (!user.isActive) {
      throw new Error('Account is deactivated');
    }

    // Verify password
    const isPasswordValid = await bcrypt.compare(password, user.passwordHash);
    if (!isPasswordValid) {
      await this.handleFailedLogin(user);
      throw new Error('Invalid credentials');
    }

    // Reset login attempts on successful login
    await this.resetLoginAttempts(user);

    // Generate tokens
    const tokens = await this.generateTokens(user);

    // Update last login
    await this.db.users.update({
      lastLoginAt: new Date(),
      lastLoginIp: ipAddress,
      lastLoginUserAgent: userAgent
    }, { where: { id: user.id } });

    // Log successful login
    await this.logAuthEvent('LOGIN_SUCCESS', user.id, {
      ipAddress,
      userAgent
    });

    return {
      user: this.sanitizeUser(user),
      tokens
    };
  }

  /**
   * Refresh access token using refresh token
   */
  async refreshToken(refreshToken) {
    try {
      const decoded = jwt.verify(refreshToken, this.jwtSecret);
      const user = await this.db.users.findByPk(decoded.userId);
      
      if (!user || !user.isActive) {
        throw new Error('Invalid refresh token');
      }

      // Generate new tokens
      const tokens = await this.generateTokens(user);
      
      // Log token refresh
      await this.logAuthEvent('TOKEN_REFRESHED', user.id);

      return { tokens };
    } catch (error) {
      throw new Error('Invalid or expired refresh token');
    }
  }

  /**
   * Logout user - invalidate refresh token
   */
  async logout(userId, refreshToken) {
    // Add refresh token to blacklist
    await this.db.blacklistedTokens.create({
      id: uuidv4(),
      token: refreshToken,
      expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000), // 7 days
      createdAt: new Date()
    });

    // Log logout
    await this.logAuthEvent('LOGOUT', userId);
  }

  /**
   * Generate JWT tokens for user
   */
  async generateTokens(user) {
    const payload = {
      userId: user.id,
      email: user.email,
      role: user.role,
      tenantId: user.tenantId
    };

    const accessToken = jwt.sign(payload, this.jwtSecret, { 
      expiresIn: this.jwtExpiry,
      issuer: 'engineering-orchestration',
      audience: user.tenantId
    });

    const refreshToken = jwt.sign(
      { userId: user.id, type: 'refresh' }, 
      this.jwtSecret, 
      { expiresIn: this.refreshTokenExpiry }
    );

    return { accessToken, refreshToken };
  }

  /**
   * Verify JWT token
   */
  async verifyToken(token) {
    try {
      const decoded = jwt.verify(token, this.jwtSecret);
      const user = await this.db.users.findByPk(decoded.userId);
      
      if (!user || !user.isActive) {
        throw new Error('User not found or inactive');
      }

      return {
        user: this.sanitizeUser(user),
        decoded
      };
    } catch (error) {
      throw new Error('Invalid token');
    }
  }

  /**
   * Handle failed login attempts
   */
  async handleFailedLogin(user) {
    const attempts = user.loginAttempts + 1;
    const lockUntil = attempts >= this.maxLoginAttempts ? Date.now() + this.lockoutTime : null;

    await this.db.users.update({
      loginAttempts: attempts,
      lockUntil
    }, { where: { id: user.id } });

    await this.logAuthEvent('LOGIN_FAILED', user.id, {
      attempts,
      locked: !!lockUntil
    });
  }

  /**
   * Reset login attempts after successful login
   */
  async resetLoginAttempts(user) {
    if (user.loginAttempts > 0) {
      await this.db.users.update({
        loginAttempts: 0,
        lockUntil: null
      }, { where: { id: user.id } });
    }
  }

  /**
   * Log authentication events
   */
  async logAuthEvent(eventType, userId, metadata = {}) {
    await this.db.authLogs.create({
      id: uuidv4(),
      eventType,
      userId,
      metadata: JSON.stringify(metadata),
      ipAddress: metadata.ipAddress,
      userAgent: metadata.userAgent,
      timestamp: new Date()
    });
  }

  /**
   * Validate email format
   */
  validateEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      throw new Error('Invalid email format');
    }
  }

  /**
   * Validate password strength
   */
  validatePassword(password) {
    if (password.length < 8) {
      throw new Error('Password must be at least 8 characters long');
    }
    
    if (!/(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])/.test(password)) {
      throw new Error('Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character');
    }
  }

  /**
   * Remove sensitive data from user object
   */
  sanitizeUser(user) {
    const { passwordHash, loginAttempts, lockUntil, ...sanitized } = user.toJSON();
    return sanitized;
  }

  /**
   * Request password reset
   */
  async requestPasswordReset(email) {
    const user = await this.db.users.findOne({ where: { email: email.toLowerCase() } });
    if (!user) {
      // Don't reveal if user exists
      return { message: 'If an account exists, a reset email has been sent' };
    }

    const resetToken = crypto.randomBytes(32).toString('hex');
    const resetTokenExpiry = new Date(Date.now() + 60 * 60 * 1000); // 1 hour

    await this.db.users.update({
      resetToken,
      resetTokenExpiry
    }, { where: { id: user.id } });

    await this.logAuthEvent('PASSWORD_RESET_REQUESTED', user.id, { email });

    // TODO: Send email with reset token
    return { message: 'If an account exists, a reset email has been sent' };
  }

  /**
   * Reset password with token
   */
  async resetPassword(resetToken, newPassword) {
    const user = await this.db.users.findOne({
      where: {
        resetToken,
        resetTokenExpiry: { [this.db.Sequelize.Op.gt]: new Date() }
      }
    });

    if (!user) {
      throw new Error('Invalid or expired reset token');
    }

    this.validatePassword(newPassword);
    const passwordHash = await bcrypt.hash(newPassword, 12);

    await this.db.users.update({
      passwordHash,
      resetToken: null,
      resetTokenExpiry: null,
      loginAttempts: 0,
      lockUntil: null
    }, { where: { id: user.id } });

    await this.logAuthEvent('PASSWORD_RESET_SUCCESS', user.id);

    return { message: 'Password reset successful' };
  }
}

module.exports = AuthService;
