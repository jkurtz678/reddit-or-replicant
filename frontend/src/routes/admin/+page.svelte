<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { adminSession } from '$lib/admin';
	
	let password = '';
	let error = '';
	let loading = false;

	// Redirect to admin posts if already logged in
	onMount(() => {
		if (adminSession.isAdmin()) {
			goto('/admin/posts');
		}
	});

	async function handleLogin() {
		if (!password.trim()) {
			error = 'Please enter admin password';
			return;
		}

		loading = true;
		error = '';

		const success = await adminSession.login(password.trim());
		
		if (success) {
			goto('/admin/posts');
		} else {
			error = 'Invalid admin password';
			password = '';
		}

		loading = false;
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter') {
			handleLogin();
		}
	}
</script>

<div class="min-h-screen text-gray-100 flex items-center justify-center" style="background: linear-gradient(180deg, #0a0a0b 0%, #111013 100%)">
	<div class="max-w-md w-full mx-auto px-8">
		<div class="text-center mb-8">
			<a href="/" class="text-2xl font-bold" style="color: #f3f4f6; text-shadow: 0 0 12px rgba(0, 212, 255, 0.1);">
				Reddit or <span class="glitch" data-text="Replicant">Replicant</span>?
			</a>
			<p class="text-gray-400 mt-4">Admin Access</p>
		</div>

		<div class="border border-gray-700 rounded-lg p-6" style="background: rgba(17, 17, 20, 0.85); backdrop-filter: blur(10px);">
			<div class="space-y-4">
				<div>
					<label for="password" class="block text-sm font-medium text-gray-300 mb-2">
						Admin Password
					</label>
					<input
						id="password"
						type="password"
						bind:value={password}
						on:keydown={handleKeydown}
						class="w-full px-3 py-2 rounded bg-gray-800 border border-gray-600 text-white placeholder-gray-400 focus:border-blue-400 focus:outline-none"
						placeholder="Enter admin password"
						disabled={loading}
					/>
				</div>

				{#if error}
					<div class="text-amber-400 text-sm">{error}</div>
				{/if}

				<button 
					on:click={handleLogin}
					disabled={loading || !password.trim()}
					class="w-full px-4 py-2 text-white rounded transition-all duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed hover:scale-105"
					style="background: linear-gradient(135deg, var(--replicant-primary), var(--replicant-secondary)); border: 1px solid var(--replicant-border);"
					on:mouseenter={(e) => !loading && !e.target.disabled && (e.target.style.boxShadow = '0 0 15px var(--replicant-glow)')}
					on:mouseleave={(e) => e.target.style.boxShadow = ''}
				>
					{loading ? 'Authenticating...' : 'Login'}
				</button>

				<div class="text-center pt-4">
					<a href="/" class="text-blue-400 hover:text-blue-300 transition-colors text-sm">
						← Back to Home
					</a>
				</div>
			</div>
		</div>
	</div>
</div>