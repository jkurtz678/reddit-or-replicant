import { browser } from '$app/environment';
import { API_BASE_URL } from './config';

// Admin environment management
export type AdminEnvironment = 'local' | 'live';

export const adminEnvironment = {
	/**
	 * Get current admin environment selection
	 */
	get(): AdminEnvironment {
		if (!browser) return 'local';
		return (localStorage.getItem('admin_environment') as AdminEnvironment) || 'local';
	},

	/**
	 * Set admin environment selection
	 */
	set(env: AdminEnvironment): void {
		if (browser) {
			localStorage.setItem('admin_environment', env);
		}
	},

	/**
	 * Get API base URL for current environment
	 * Always use local backend when running locally - only the database target changes
	 */
	getApiUrl(): string {
		// Always use local backend when running locally
		// The environment toggle only affects which database the backend uses
		return 'http://localhost:8000';
	},

	/**
	 * Get headers for admin API requests
	 */
	getHeaders(): Record<string, string> {
		const env = this.get();
		return {
			'Content-Type': 'application/json',
			'X-Admin-Env': env
		};
	}
};

// Simple admin session management using localStorage
export const adminSession = {
	/**
	 * Attempt to login with admin password
	 */
	async login(password: string): Promise<boolean> {
		if (!browser) return false;
		
		try {
			const response = await fetch(`${adminEnvironment.getApiUrl()}/api/admin/login`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({ password })
			});

			if (response.ok) {
				const data = await response.json();
				localStorage.setItem('admin_token', data.token);
				return true;
			}
			return false;
		} catch (error) {
			console.error('Admin login failed:', error);
			return false;
		}
	},

	/**
	 * Logout and clear admin session
	 */
	logout(): void {
		if (browser) {
			localStorage.removeItem('admin_token');
		}
	},

	/**
	 * Check if current user is admin
	 */
	isAdmin(): boolean {
		if (!browser) return false;
		
		const token = localStorage.getItem('admin_token');
		return token === 'admin_authenticated';
	},

	/**
	 * Get admin token for API requests
	 */
	getToken(): string | null {
		if (!browser) return null;
		
		return localStorage.getItem('admin_token');
	}
};