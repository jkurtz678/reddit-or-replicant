// Simple admin session management using localStorage
export const adminSession = {
	/**
	 * Attempt to login with admin password
	 */
	async login(password: string): Promise<boolean> {
		try {
			const response = await fetch('/api/admin/login', {
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
		localStorage.removeItem('admin_token');
	},

	/**
	 * Check if current user is admin
	 */
	isAdmin(): boolean {
		const token = localStorage.getItem('admin_token');
		return token === 'admin_authenticated';
	},

	/**
	 * Get admin token for API requests
	 */
	getToken(): string | null {
		return localStorage.getItem('admin_token');
	}
};