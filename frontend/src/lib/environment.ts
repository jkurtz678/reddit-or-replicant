import { browser } from '$app/environment';

export type Database = 'local' | 'live';

/**
 * Check if we're running in local development environment (localhost)
 */
export function isLocalEnvironment(): boolean {
	if (!browser) return false;

	// Check if running on localhost
	return window.location.hostname === 'localhost' ||
	       window.location.hostname === '127.0.0.1';
}

/**
 * Database management for local development
 */
export const databaseManager = {
	/**
	 * Get current database selection (only available in local environment)
	 */
	get(): Database {
		if (!browser || !isLocalEnvironment()) return 'local';
		return (localStorage.getItem('dev_database') as Database) || 'local';
	},

	/**
	 * Set database selection (only available in local environment)
	 */
	set(database: Database): void {
		if (browser && isLocalEnvironment()) {
			localStorage.setItem('dev_database', database);
		}
	},

	/**
	 * Get API base URL - always uses local backend in development
	 */
	getApiUrl(): string {
		if (isLocalEnvironment()) {
			return 'http://localhost:8000';
		}
		// In production environment, use production backend
		return 'https://replicant-backend.fly.dev';
	},

	/**
	 * Get headers for API requests including database selection
	 */
	getHeaders(): Record<string, string> {
		const headers: Record<string, string> = {
			'Content-Type': 'application/json'
		};

		// Add database header only in local environment
		if (isLocalEnvironment()) {
			headers['X-Admin-Env'] = this.get();
		}

		return headers;
	}
};