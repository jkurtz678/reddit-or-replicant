import { browser } from '$app/environment';
import { API_BASE_URL } from './config';

// Simple admin session management using localStorage
export const adminSession = {
	/**
	 * Attempt to login with admin password
	 */
	async login(password: string): Promise<boolean> {
		if (!browser) return false;
		
		try {
			const response = await fetch(`${API_BASE_URL}/api/admin/login`, {
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