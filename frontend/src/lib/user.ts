import { browser } from '$app/environment';
import { API_BASE_URL } from './config';

// Anonymous user management using localStorage
export const userManager = {
	/**
	 * Generate a random anonymous user ID
	 */
	generateUserId(): string {
		return 'user_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now().toString(36);
	},

	/**
	 * Get the current user ID, creating one if it doesn't exist
	 */
	getUserId(): string {
		if (!browser) {
			return ''; // Return empty string during SSR - caller should check browser
		}
		
		let user_id = localStorage.getItem('anonymous_user_id');
		
		if (!user_id) {
			user_id = this.generateUserId();
			localStorage.setItem('anonymous_user_id', user_id);
			
			// Register this new user with the backend
			this.registerUser(user_id).catch(error => {
				console.error('Failed to register user:', error);
			});
		}
		
		return user_id;
	},

	/**
	 * Register a new anonymous user with the backend
	 */
	async registerUser(user_id: string): Promise<void> {
		if (!browser) return;
		
		try {
			const response = await fetch(`${API_BASE_URL}/api/users/register`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({ anonymous_id: user_id })
			});

			if (!response.ok) {
				throw new Error('Failed to register user');
			}
		} catch (error) {
			console.error('User registration error:', error);
			// Don't throw - we can still function without backend registration
		}
	},

	/**
	 * Clear user data (for testing or reset purposes)
	 */
	clearUser(): void {
		if (browser) {
			localStorage.removeItem('anonymous_user_id');
		}
	}
};