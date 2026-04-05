/**
 * Authentication Routes - Express.js
 * Handles all authentication endpoints
 */

const express = require('express');
const { body, validationResult } = require('express-validator');
const rateLimit = require('express-rate-limit');
const AuthService = require('./auth-service');
const AuthMiddleware = require('./auth-middleware');

class AuthRoutes {
  constructor(authService) {
    this.authService = authService;
    this.middleware = new AuthMiddleware(authService);
    this.router = express.Router();
    this.setupRoutes();
  }

  setupRoutes() {
    // Rate limiting for auth endpoints
    const authLimiter = rateLimit({
      windowMs: 15 * 60 * 1000, // 15 minutes
      max: 5, // 5 attempts per window
      message: 'Too many authentication attempts, please try again later',
      standardHeaders: true,
      legacyHeaders: false,
    });

    const passwordLimiter = rateLimit({
      windowMs: 60 * 60 * 1000, // 1 hour
      max: 3, // 3 password reset requests per hour
      message: 'Too many password reset attempts, please try again later',
      standardHeaders: true,
      legacyHeaders: false,
    });

    // Register new user
    this.router.post('/register', 
      authLimiter,
      [
        body('email')
          .isEmail()
          .normalizeEmail()
          .withMessage('Valid email is required'),
        body('password')
          .isLength({ min: 8 })
          .withMessage('Password must be at least 8 characters long')
          .matches(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])/)
          .withMessage('Password must contain uppercase, lowercase, number, and special character'),
        body('firstName')
          .trim()
          .isLength({ min: 1, max: 50 })
          .withMessage('First name is required (max 50 characters)'),
        body('lastName')
          .trim()
          .isLength({ min: 1, max: 50 })
          .withMessage('Last name is required (max 50 characters)'),
        body('role')
          .optional()
          .isIn(['admin', 'creator', 'viewer'])
          .withMessage('Role must be admin, creator, or viewer')
      ],
      this.handleValidationErrors,
      this.register.bind(this)
    );

    // Login
    this.router.post('/login',
      authLimiter,
      [
        body('email')
          .isEmail()
          .normalizeEmail()
          .withMessage('Valid email is required'),
        body('password')
          .notEmpty()
          .withMessage('Password is required')
      ],
      this.handleValidationErrors,
      this.login.bind(this)
    );

    // Refresh token
    this.router.post('/refresh',
      [
        body('refreshToken')
          .notEmpty()
          .withMessage('Refresh token is required')
      ],
      this.handleValidationErrors,
      this.refreshToken.bind(this)
    );

    // Logout
    this.router.post('/logout',
      this.middleware.authenticate(),
      [
        body('refreshToken')
          .notEmpty()
          .withMessage('Refresh token is required')
      ],
      this.handleValidationErrors,
      this.logout.bind(this)
    );

    // Request password reset
    this.router.post('/request-password-reset',
      passwordLimiter,
      [
        body('email')
          .isEmail()
          .normalizeEmail()
          .withMessage('Valid email is required')
      ],
      this.handleValidationErrors,
      this.requestPasswordReset.bind(this)
    );

    // Reset password
    this.router.post('/reset-password',
      [
        body('resetToken')
          .notEmpty()
          .withMessage('Reset token is required'),
        body('newPassword')
          .isLength({ min: 8 })
          .withMessage('Password must be at least 8 characters long')
          .matches(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])/)
          .withMessage('Password must contain uppercase, lowercase, number, and special character')
      ],
      this.handleValidationErrors,
      this.resetPassword.bind(this)
    );

    // Verify token (for client-side token validation)
    this.router.get('/verify',
      this.middleware.authenticate(),
      this.verifyToken.bind(this)
    );

    // Get current user profile
    this.router.get('/profile',
      this.middleware.authenticate(),
      this.getProfile.bind(this)
    );

    // Update user profile
    this.router.put('/profile',
      this.middleware.authenticate(),
      [
        body('firstName')
          .optional()
          .trim()
          .isLength({ min: 1, max: 50 })
          .withMessage('First name must be 1-50 characters'),
        body('lastName')
          .optional()
          .trim()
          .isLength({ min: 1, max: 50 })
          .withMessage('Last name must be 1-50 characters'),
        body('email')
          .optional()
          .isEmail()
          .normalizeEmail()
          .withMessage('Valid email is required')
      ],
      this.handleValidationErrors,
      this.updateProfile.bind(this)
    );

    // Change password
    this.router.put('/change-password',
      this.middleware.authenticate(),
      [
        body('currentPassword')
          .notEmpty()
          .withMessage('Current password is required'),
        body('newPassword')
          .isLength({ min: 8 })
          .withMessage('Password must be at least 8 characters long')
          .matches(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])/)
          .withMessage('Password must contain uppercase, lowercase, number, and special character')
      ],
      this.handleValidationErrors,
      this.changePassword.bind(this)
    );
  }

  async register(req, res) {
    try {
      const result = await this.authService.register(req.body);
      
      res.status(201).json({
        success: true,
        message: 'User registered successfully',
        data: result
      });
    } catch (error) {
      res.status(400).json({
        success: false,
        error: error.message,
        code: 'REGISTRATION_FAILED'
      });
    }
  }

  async login(req, res) {
    try {
      const { email, password } = req.body;
      const ipAddress = req.ip;
      const userAgent = req.get('User-Agent');
      
      const result = await this.authService.login(email, password, ipAddress, userAgent);
      
      res.json({
        success: true,
        message: 'Login successful',
        data: result
      });
    } catch (error) {
      res.status(401).json({
        success: false,
        error: error.message,
        code: 'LOGIN_FAILED'
      });
    }
  }

  async refreshToken(req, res) {
    try {
      const { refreshToken } = req.body;
      const result = await this.authService.refreshToken(refreshToken);
      
      res.json({
        success: true,
        message: 'Token refreshed successfully',
        data: result
      });
    } catch (error) {
      res.status(401).json({
        success: false,
        error: error.message,
        code: 'TOKEN_REFRESH_FAILED'
      });
    }
  }

  async logout(req, res) {
    try {
      const { refreshToken } = req.body;
      await this.authService.logout(req.user.id, refreshToken);
      
      res.json({
        success: true,
        message: 'Logout successful'
      });
    } catch (error) {
      res.status(500).json({
        success: false,
        error: error.message,
        code: 'LOGOUT_FAILED'
      });
    }
  }

  async requestPasswordReset(req, res) {
    try {
      const { email } = req.body;
      const result = await this.authService.requestPasswordReset(email);
      
      res.json({
        success: true,
        message: result.message
      });
    } catch (error) {
      res.status(500).json({
        success: false,
        error: error.message,
        code: 'PASSWORD_RESET_REQUEST_FAILED'
      });
    }
  }

  async resetPassword(req, res) {
    try {
      const { resetToken, newPassword } = req.body;
      const result = await this.authService.resetPassword(resetToken, newPassword);
      
      res.json({
        success: true,
        message: result.message
      });
    } catch (error) {
      res.status(400).json({
        success: false,
        error: error.message,
        code: 'PASSWORD_RESET_FAILED'
      });
    }
  }

  async verifyToken(req, res) {
    res.json({
      success: true,
      message: 'Token is valid',
      data: {
        user: req.user,
        token: req.token
      }
    });
  }

  async getProfile(req, res) {
    try {
      // Get additional user data if needed
      const user = await this.authService.db.users.findByPk(req.user.id, {
        attributes: { exclude: ['passwordHash', 'resetToken'] },
        include: [
          {
            model: this.authService.db.tenants,
            as: 'tenant',
            attributes: ['id', 'name', 'plan', 'createdAt']
          }
        ]
      });

      res.json({
        success: true,
        data: { user }
      });
    } catch (error) {
      res.status(500).json({
        success: false,
        error: error.message,
        code: 'PROFILE_FETCH_FAILED'
      });
    }
  }

  async updateProfile(req, res) {
    try {
      const { firstName, lastName, email } = req.body;
      const userId = req.user.id;

      // Check if email is being changed and if it's already taken
      if (email && email !== req.user.email) {
        const existingUser = await this.authService.db.users.findOne({
          where: { email: email.toLowerCase() }
        });

        if (existingUser) {
          return res.status(400).json({
            success: false,
            error: 'Email is already in use',
            code: 'EMAIL_ALREADY_IN_USE'
          });
        }
      }

      // Update user
      const updateData = {};
      if (firstName) updateData.firstName = firstName;
      if (lastName) updateData.lastName = lastName;
      if (email) updateData.email = email.toLowerCase();
      updateData.updatedAt = new Date();

      await this.authService.db.users.update(updateData, {
        where: { id: userId }
      });

      // Get updated user
      const updatedUser = await this.authService.db.users.findByPk(userId, {
        attributes: { exclude: ['passwordHash', 'resetToken'] }
      });

      res.json({
        success: true,
        message: 'Profile updated successfully',
        data: { user: updatedUser }
      });
    } catch (error) {
      res.status(500).json({
        success: false,
        error: error.message,
        code: 'PROFILE_UPDATE_FAILED'
      });
    }
  }

  async changePassword(req, res) {
    try {
      const { currentPassword, newPassword } = req.body;
      const userId = req.user.id;

      // Get user with password
      const user = await this.authService.db.users.findByPk(userId);
      
      // Verify current password
      const bcrypt = require('bcryptjs');
      const isCurrentPasswordValid = await bcrypt.compare(currentPassword, user.passwordHash);
      
      if (!isCurrentPasswordValid) {
        return res.status(400).json({
          success: false,
          error: 'Current password is incorrect',
          code: 'INVALID_CURRENT_PASSWORD'
        });
      }

      // Hash new password
      const saltRounds = 12;
      const newPasswordHash = await bcrypt.hash(newPassword, saltRounds);

      // Update password
      await this.authService.db.users.update({
        passwordHash: newPasswordHash,
        updatedAt: new Date()
      }, { where: { id: userId } });

      // Log password change
      await this.authService.logAuthEvent('PASSWORD_CHANGED', userId);

      res.json({
        success: true,
        message: 'Password changed successfully'
      });
    } catch (error) {
      res.status(500).json({
        success: false,
        error: error.message,
        code: 'PASSWORD_CHANGE_FAILED'
      });
    }
  }

  handleValidationErrors(req, res, next) {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({
        success: false,
        error: 'Validation failed',
        code: 'VALIDATION_ERROR',
        details: errors.array()
      });
    }
    next();
  }

  getRouter() {
    return this.router;
  }
}

module.exports = AuthRoutes;
