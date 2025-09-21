<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { adminSession } from '$lib/admin';
	import { userManager } from '$lib/user';
	import { browser } from '$app/environment';

	interface PostListItem {
		id: number;
		reddit_url: string;
		title: string;
		subreddit: string;
		ai_count: number;
		total_count: number;
		created_at: string;
	}
	
	interface UserProgress {
		total_guesses: number;
		correct_guesses: number;
		accuracy: number;
	}

	let posts: PostListItem[] = [];
	let loading = true;
	let submitting = false;
	let error = '';
	let redditUrl = '';
	let showSubmitDialog = false;
	let dialogVisible = false;
	let userProgress: Record<number, UserProgress> = {};
	let anonymousUserId = '';
	let progressLoaded = false;

	// Check if user is admin
	$: isAdmin = adminSession.isAdmin();

	// Handle dialog opening with transition
	function openDialog() {
		showSubmitDialog = true;
		setTimeout(() => dialogVisible = true, 10); // Small delay for transition
	}

	// Handle dialog closing with transition  
	function closeDialog() {
		dialogVisible = false;
		setTimeout(() => showSubmitDialog = false, 300); // Wait for fade out
	}

	// Initialize user ID when in browser
	$: if (browser && !anonymousUserId) {
		anonymousUserId = userManager.getUserId();
	}
	
	// Load user progress when user ID is available and not already loaded
	$: if (browser && anonymousUserId && !progressLoaded) {
		loadUserProgress();
	}
	
	// Load the list of posts on page mount
	onMount(async () => {
		await loadPosts();
	});

	async function loadPosts() {
		try {
			loading = true;
			const response = await fetch('/api/posts');
			if (!response.ok) throw new Error('Failed to fetch posts');
			const data = await response.json();
			posts = data.posts || [];
		} catch (err) {
			error = 'Failed to load posts';
			console.error(err);
		} finally {
			loading = false;
		}
	}
	
	async function loadUserProgress() {
		if (!browser || !anonymousUserId || progressLoaded) return;
		
		try {
			const response = await fetch(`/api/users/${anonymousUserId}/progress`);
			if (!response.ok) {
				console.error('Failed to load user progress');
				return;
			}
			
			const data = await response.json();
			userProgress = data.progress || {};
			progressLoaded = true;
			
		} catch (err) {
			console.error('Error loading user progress:', err);
		}
	}
	
	// Function to get progress status for a post
	function getProgressStatus(postId: number, totalComments: number): 'not-started' | 'in-progress' | 'completed' {
		const progress = userProgress[postId];
		if (!progress || progress.total_guesses === 0) {
			return 'not-started';
		}
		if (progress.total_guesses >= totalComments) {
			return 'completed';
		}
		return 'in-progress';
	}
	
	// Function to get progress percentage
	function getProgressPercentage(postId: number, totalComments: number): number {
		const progress = userProgress[postId];
		if (!progress || progress.total_guesses === 0) {
			return 0;
		}
		return Math.round((progress.total_guesses / totalComments) * 100);
	}

	async function submitRedditUrl() {
		if (!redditUrl.trim()) return;
		
		try {
			submitting = true;
			error = '';
			
			const response = await fetch('/api/posts/submit', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify({ url: redditUrl.trim() }),
			});
			
			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || 'Failed to submit URL');
			}
			
			const result = await response.json();
			console.log('Submitted successfully:', result);
			
			// Clear the input, close dialog, and reload posts
			redditUrl = '';
			closeDialog();
			await loadPosts();
			
			// Reload progress if we have a user ID
			if (browser && anonymousUserId) {
				progressLoaded = false; // This will trigger reactive reload
			}
			
			// Navigate to the test page with the new post
			if (result.id) {
				goto(`/test?post=${result.id}`);
			}
			
		} catch (err: any) {
			error = err.message;
			console.error(err);
		} finally {
			submitting = false;
		}
	}

	function playGame(postId: number) {
		goto(`/test?post=${postId}`);
	}
</script>

<div class="min-h-screen text-gray-100" style="background: linear-gradient(180deg, #0a0a0b 0%, #111013 100%)">
	<!-- Fixed Toolbar -->
	<div class="fixed top-0 left-0 right-0 z-50 border-b border-gray-700" style="background: rgba(17, 17, 20, 0.95); backdrop-filter: blur(10px);">
		<div class="max-w-4xl mx-auto px-4 md:px-0 py-3">
			<div class="flex items-center justify-between">
				<a href="/" class="text-lg font-bold cursor-pointer hover:text-blue-300 transition-colors" style="color: #f3f4f6; text-shadow: 0 0 8px rgba(0, 212, 255, 0.1);">
					Reddit or <span class="glitch" data-text="Replicant">Replicant</span>?
				</a>
				{#if isAdmin}
					<div class="flex items-center gap-2">
						<span class="text-sm text-amber-400">Admin</span>
						<a href="/admin/posts" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">
							Manage
						</a>
					</div>
				{/if}
			</div>
		</div>
	</div>

	<!-- Content with top padding to account for fixed toolbar -->
	<div class="pt-16">
	<div class="container mx-auto p-8 md:px-0">

		<!-- Posts List -->
		{#if loading}
			<div class="text-center">
				<div class="animate-pulse text-gray-300">Loading posts...</div>
			</div>
		{:else if posts.length > 0}
			<div class="max-w-4xl mx-auto">
				<div class="flex justify-between items-center mb-6">
					<h2 class="text-xl font-semibold text-white">Replicants are hiding among these Reddit posts</h2>
					{#if isAdmin}
						<button 
							on:click={openDialog}
							class="px-4 py-2 text-white rounded transition-all duration-200 cursor-pointer hover:scale-105"
							style="background: linear-gradient(135deg, var(--replicant-primary), var(--replicant-secondary)); border: 1px solid var(--replicant-border);"
							on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px var(--replicant-glow)'}
							on:mouseleave={(e) => e.target.style.boxShadow = ''}
						>
							+ Add New Post
						</button>
					{/if}
				</div>
				<div class="grid gap-4">
					{#each posts as post}
						{@const progressStatus = getProgressStatus(post.id, post.total_count)}
						{@const userPostProgress = userProgress[post.id]}
						<div 
							class="border border-gray-700 rounded-lg p-6 cursor-pointer transition-all duration-200 hover:border-blue-400 hover:scale-[1.02]"
							style="background: rgba(17, 17, 20, 0.85); backdrop-filter: blur(10px);"
							on:click={() => playGame(post.id)}
							on:keydown={(e) => e.key === 'Enter' && playGame(post.id)}
							role="button"
							tabindex="0"
						>
							<div class="flex justify-between items-start">
								<div class="flex-1">
									<h3 class="font-medium text-white mb-2 text-lg">{post.title}</h3>
									<div class="text-sm text-gray-400">
										<span style="color: #00d4ff;">r/{post.subreddit}</span>
										• {post.total_count} comments
									</div>
								</div>
								<div class="ml-4 flex flex-col items-end">
									<button 
										class="px-3 py-1 text-white rounded text-sm transition-all duration-200 hover:scale-105 cursor-pointer mb-2"
										style="background: linear-gradient(135deg, {progressStatus === 'completed' ? 'var(--replicant-dark), var(--replicant-light)' : 'var(--replicant-primary), var(--replicant-secondary)'}); border: 1px solid var(--replicant-border);"
										on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px var(--replicant-glow)'}
										on:mouseleave={(e) => e.target.style.boxShadow = ''}
									>
										{#if progressStatus === 'completed'}
											Review ({Math.round(userPostProgress.accuracy * 100)}% accuracy)
										{:else if progressStatus === 'in-progress'}
											Continue
										{:else}
											Begin Test
										{/if}
									</button>
									{#if userPostProgress && userPostProgress.total_guesses > 0}
										<div class="text-xs text-gray-400">
											{userPostProgress.total_guesses} guessed ({userPostProgress.correct_guesses} correct)
										</div>
									{/if}
								</div>
							</div>
						</div>
					{/each}
				</div>
			</div>
		{:else}
			<div class="text-center text-gray-400">
				{#if isAdmin}
					<p class="mb-4">No posts yet. Add your first Reddit post to get started!</p>
					<button 
						on:click={openDialog}
						class="px-6 py-3 text-white rounded transition-all duration-200 cursor-pointer hover:scale-105"
						style="background: linear-gradient(135deg, var(--replicant-primary), var(--replicant-secondary)); border: 1px solid var(--replicant-border);"
						on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px var(--replicant-glow)'}
						on:mouseleave={(e) => e.target.style.boxShadow = ''}
					>
						+ Add Your First Post
					</button>
				{:else}
					<p class="mb-4">No posts available yet. Check back soon!</p>
					<div class="text-sm text-gray-500">
						Posts will be curated and added by our team for the best experience.
					</div>
				{/if}
			</div>
		{/if}
	</div>
	</div>
</div>

<!-- Submit Dialog (Admin only) -->
{#if showSubmitDialog && isAdmin}
	<div 
		class="fixed inset-0 flex items-center justify-center z-50 transition-opacity duration-300"
		class:opacity-0={!dialogVisible}
		class:opacity-100={dialogVisible}
		style="background: rgba(0, 0, 0, 0.3); backdrop-filter: blur(2px);"
		on:click={closeDialog}
	>
		<div 
			class="border border-gray-700 rounded-lg p-6 m-4 max-w-2xl w-full transform transition-all duration-300"
			class:scale-95={!dialogVisible}
			class:opacity-0={!dialogVisible}
			class:scale-100={dialogVisible}
			class:opacity-100={dialogVisible}
			style="background: rgba(17, 17, 20, 0.95); backdrop-filter: blur(10px);" 
			on:click|stopPropagation
		>
			<div class="flex justify-between items-center mb-4">
				<h2 class="text-lg font-semibold text-white">Submit New Reddit Post</h2>
				<button 
					on:click={closeDialog}
					class="text-gray-400 hover:text-white transition-colors"
				>
					✕
				</button>
			</div>
			
			<div class="flex gap-3">
				<input 
					bind:value={redditUrl}
					placeholder="https://www.reddit.com/r/subreddit/comments/xyz/title/"
					class="flex-1 px-3 py-2 rounded bg-gray-800 border border-gray-600 text-white placeholder-gray-400 focus:border-blue-400 focus:outline-none"
					disabled={submitting}
					on:keydown={(e) => e.key === 'Enter' && submitRedditUrl()}
				/>
				<button 
					on:click={submitRedditUrl}
					disabled={submitting || !redditUrl.trim()}
					class="px-4 py-2 text-white rounded transition-all duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed hover:scale-105"
					style="background: linear-gradient(135deg, var(--replicant-primary), var(--replicant-secondary)); border: 1px solid var(--replicant-border);"
					on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px var(--replicant-glow)'}
					on:mouseleave={(e) => e.target.style.boxShadow = ''}
				>
					{submitting ? 'Processing...' : 'Submit & Play'}
				</button>
			</div>
			
			{#if error}
				<div class="mt-3 text-amber-400 text-sm">{error}</div>
			{/if}
			
			<div class="mt-3 text-gray-400 text-sm">
				Paste any Reddit post URL. We'll fetch the comments, generate AI comments, and create a guessing game.
			</div>
		</div>
	</div>
{/if}