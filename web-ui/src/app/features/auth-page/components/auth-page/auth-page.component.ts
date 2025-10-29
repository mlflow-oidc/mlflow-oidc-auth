import { Component, OnInit, inject } from '@angular/core';
import { trigger, state, style, transition, animate } from '@angular/animations';
import { RuntimeConfig } from '../../../../core/models/runtime-config.interface';
import { ActivatedRoute } from '@angular/router';

interface ProcessedError {
  message: string;
  type: 'provider' | 'security' | 'session' | 'authorization' | 'token' | 'profile' | 'database' | 'general';
  severity: 'error' | 'warning';
  action?: string;
}

@Component({
  selector: 'ml-auth-page',
  templateUrl: './auth-page.component.html',
  styleUrls: ['./auth-page.component.scss'],
  standalone: false,
  animations: [
    trigger('slideIn', [
      transition(':enter', [
        style({ opacity: 0, transform: 'translate(-50%, -60%)' }),
        animate('300ms ease-out', style({ opacity: 1, transform: 'translate(-50%, -50%)' }))
      ])
    ])
  ]
})
export class AuthPageComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);

  config: RuntimeConfig | null = null;
  processedErrors: ProcessedError[] = [];
  loginUrl = '/login';

  ngOnInit(): void {
    // Get config from route data
    this.config = this.route.snapshot.data['config'] || null;

    // Get and process error messages from query params
    this.processErrorMessages();

    // If no errors were found, also check window.location.hash for direct access
    if (this.processedErrors.length === 0) {
      this.processErrorsFromHash();
    }

    // Construct login URL based on config
    if (this.config?.basePath) {
      this.loginUrl = `${this.config.basePath}/login`;
    }
  }

  /**
   * Process errors from window.location.hash as a fallback
   * This handles the case where users access the error URL directly
   */
  private processErrorsFromHash(): void {
    const hash = window.location.hash;
    const hashMatch = hash.match(/#\/auth\?(.+)/);

    if (hashMatch && hashMatch[1]) {
      const params = new URLSearchParams(hashMatch[1]);
      const errors = params.getAll('error');

      if (errors.length > 0) {
        this.processedErrors = errors
          .map(error => this.decodeAndProcessError(error))
          .filter(error => error !== null) as ProcessedError[];
      }
    }
  }

  /**
   * Process error messages from URL query parameters
   */
  private processErrorMessages(): void {
    const errors = this.route.snapshot.queryParams['error'];
    if (!errors) {
      return;
    }

    // Handle both single error and array of errors
    const errorArray = Array.isArray(errors) ? errors : [errors];
    this.processedErrors = errorArray
      .map(error => this.decodeAndProcessError(error))
      .filter(error => error !== null) as ProcessedError[];
  }

  /**
   * Decode URL-encoded error message and categorize it
   */
  private decodeAndProcessError(encodedError: string): ProcessedError | null {
    try {
      // Decode URL-encoded message
      const decodedMessage = decodeURIComponent(encodedError);

      // Clean up the message
      const cleanMessage = this.cleanErrorMessage(decodedMessage);

      // Categorize the error
      const errorType = this.categorizeError(cleanMessage);

      // Determine severity and action
      const severity = this.determineSeverity(errorType);
      const action = this.suggestAction(errorType);

      return {
        message: cleanMessage,
        type: errorType,
        severity,
        action
      };
    } catch (error) {
      console.error('Failed to decode error message:', error);
      return {
        message: 'An unexpected error occurred during authentication.',
        type: 'general',
        severity: 'error'
      };
    }
  }

  /**
   * Clean up error message for better presentation
   */
  private cleanErrorMessage(message: string): string {
    // Remove redundant prefixes
    const prefixesToRemove = [
      'OIDC provider error: ',
      'OIDC error: ',
      'OIDC token error: ',
      'Security error: ',
      'Session error: ',
      'Authorization error: ',
      'User profile error: ',
      'User/group DB error: '
    ];

    let cleanMessage = message;
    for (const prefix of prefixesToRemove) {
      if (cleanMessage.startsWith(prefix)) {
        cleanMessage = cleanMessage.substring(prefix.length);
        break;
      }
    }

    // Capitalize first letter
    cleanMessage = cleanMessage.charAt(0).toUpperCase() + cleanMessage.slice(1);

    // Ensure message ends with a period
    if (!cleanMessage.endsWith('.')) {
      cleanMessage += '.';
    }

    return cleanMessage;
  }

  /**
   * Categorize error based on content
   */
  private categorizeError(message: string): ProcessedError['type'] {
    const lowerMessage = message.toLowerCase();

    if (lowerMessage.includes('provider') || lowerMessage.includes('authorization server')) {
      return 'provider';
    }
    if (lowerMessage.includes('csrf') || lowerMessage.includes('state') || lowerMessage.includes('security')) {
      return 'security';
    }
    if (lowerMessage.includes('session') || lowerMessage.includes('oauth state')) {
      return 'session';
    }
    if (lowerMessage.includes('not allowed') || lowerMessage.includes('authorization') || lowerMessage.includes('denied')) {
      return 'authorization';
    }
    if (lowerMessage.includes('token') || lowerMessage.includes('code')) {
      return 'token';
    }
    if (lowerMessage.includes('email') || lowerMessage.includes('profile') || lowerMessage.includes('userinfo')) {
      return 'profile';
    }
    if (lowerMessage.includes('database') || lowerMessage.includes('db')) {
      return 'database';
    }

    return 'general';
  }

  /**
   * Determine error severity
   */
  private determineSeverity(errorType: ProcessedError['type']): ProcessedError['severity'] {
    switch (errorType) {
      case 'security':
      case 'authorization':
        return 'error';
      case 'session':
      case 'token':
        return 'warning';
      default:
        return 'error';
    }
  }

  /**
   * Suggest action based on error type
   */
  private suggestAction(errorType: ProcessedError['type']): string | undefined {
    switch (errorType) {
      case 'provider':
        return 'Please contact your system administrator if this issue persists.';
      case 'security':
        return 'Please try logging in again for security reasons.';
      case 'session':
        return 'Please clear your browser cache and try again.';
      case 'authorization':
        return 'Contact your administrator to request access permissions.';
      case 'token':
        return 'Please try the authentication process again.';
      case 'profile':
        return 'Ensure your account has the required profile information.';
      case 'database':
        return 'Please try again later or contact support.';
      default:
        return 'Please try again or contact support if the issue persists.';
    }
  }

  /**
   * Get icon for error type
   */
  getErrorIcon(errorType: ProcessedError['type']): string {
    switch (errorType) {
      case 'provider':
        return 'cloud_off';
      case 'security':
        return 'security';
      case 'session':
        return 'access_time';
      case 'authorization':
        return 'block';
      case 'token':
        return 'vpn_key';
      case 'profile':
        return 'account_circle';
      case 'database':
        return 'storage';
      default:
        return 'error';
    }
  }

  /**
   * Get CSS class for error type
   */
  getErrorClass(error: ProcessedError): string {
    return `error-${error.type} severity-${error.severity}`;
  }

  /**
   * Clear all errors
   */
  clearErrors(): void {
    this.processedErrors = [];
  }

  /**
   * Track by function for ngFor
   */
  trackByIndex(index: number): number {
    return index;
  }

  /**
   * Navigate to home page
   */
  goHome(): void {
    window.location.href = '/';
  }

  /**
   * Get the provider display name
   */
  get providerDisplayName(): string {
    return this.config?.provider || 'Login with Test';
  }

  /**
   * Check if there are any errors to display
   */
  get hasErrors(): boolean {
    return this.processedErrors.length > 0;
  }
}
