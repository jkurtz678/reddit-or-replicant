<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { userManager } from '$lib/user';
	import { browser } from '$app/environment';
	import { databaseManager, isLocalEnvironment } from '$lib/environment';
	import DatabaseSelector from '$lib/components/DatabaseSelector.svelte';

	// Close dropdown when clicking outside
	function handleClickOutside(event: MouseEvent) {
		if (openDropdownId !== null) {
			const target = event.target as HTMLElement;
			if (!target.closest('.relative')) {
				closeDropdown();
			}
		}
	}

	interface PostListItem {
		id: number;
		reddit_url: string;
		title: string;
		subreddit: string;
		ai_count: number;
		total_count: number;
		created_at: string;
		deleted_at?: string;
		is_deleted?: number;
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
	let overwriteExisting = false;
	let showSubmitDialog = false;
	let dialogVisible = false;
	let userProgress: Record<number, UserProgress> = {};
	let anonymousUserId = '';
	let progressLoaded = false;
	let currentSubreddit = '';
	let openDropdownId: number | null = null;

	// Get subreddit from URL params
	$: currentSubreddit = $page.params.subreddit || '';

	// Check if we're in local environment (admin features available)
	$: showAdminFeatures = isLocalEnvironment();

	// Initialize user ID when in browser
	$: if (browser && !anonymousUserId) {
		anonymousUserId = userManager.getUserId();
	}

	// Load everything when subreddit changes or user ID becomes available
	$: if (currentSubreddit && browser && anonymousUserId) {
		loadAllData();
	}

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

	// Load data on mount
	onMount(async () => {
		// Wait a tick for reactive statements to run
		await new Promise(resolve => setTimeout(resolve, 0));
		// Only load if we have the subreddit - the reactive statement will handle the rest
		if (currentSubreddit && browser && anonymousUserId) {
			await loadAllData();
		}

		// Add click outside handler
		if (browser) {
			document.addEventListener('click', handleClickOutside);
			return () => {
				document.removeEventListener('click', handleClickOutside);
			};
		}
	});

	async function loadPosts() {
		if (!currentSubreddit) return [];

		try {
			// Include deleted posts for admin users in local environment
			const includeDeleted = showAdminFeatures ? '?include_deleted=true' : '';
			const response = await fetch(`${databaseManager.getApiUrl()}/api/posts/subreddit/${currentSubreddit}${includeDeleted}`, {
				headers: databaseManager.getHeaders()
			});
			if (!response.ok) throw new Error('Failed to fetch posts');
			const data = await response.json();
			return data.posts || [];
		} catch (err) {
			console.error('Error loading posts:', err);
			throw err;
		}
	}

	async function loadUserProgress() {
		if (!browser || !anonymousUserId) return {};

		try {
			const response = await fetch(`${databaseManager.getApiUrl()}/api/users/${anonymousUserId}/progress`, {
				headers: databaseManager.getHeaders()
			});
			if (!response.ok) {
				throw new Error('Failed to load user progress');
			}

			const data = await response.json();
			return data.progress || {};

		} catch (err) {
			console.error('Error loading user progress:', err);
			throw err;
		}
	}

	async function loadAllData() {
		if (!currentSubreddit || !browser || !anonymousUserId) return;

		try {
			loading = true;
			error = '';

			// Run both API calls in parallel
			const [postsData, progressData] = await Promise.all([
				loadPosts(),
				loadUserProgress()
			]);

			// Update state only after both complete successfully
			posts = postsData;
			userProgress = progressData;
			progressLoaded = true;

		} catch (err: any) {
			error = err.message || 'Failed to load data';
			console.error('Error loading data:', err);
			// Reset state on error
			posts = [];
			userProgress = {};
			progressLoaded = false;
		} finally {
			loading = false;
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

	async function submitRedditUrl() {
		if (!redditUrl.trim()) return;

		try {
			submitting = true;
			error = '';

			const response = await fetch(`${databaseManager.getApiUrl()}/api/posts/submit`, {
				method: 'POST',
				headers: databaseManager.getHeaders(),
				body: JSON.stringify({
					url: redditUrl.trim(),
					overwrite_existing: overwriteExisting
				}),
			});

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || 'Failed to submit URL');
			}

			const result = await response.json();
			console.log('Submitted successfully:', result);

			// Clear the input, close dialog, and reload data
			redditUrl = '';
			overwriteExisting = false;
			closeDialog();
			await loadAllData();

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

	async function deletePost(postId: number) {
		if (!confirm('Are you sure you want to delete this post? It can be restored later.')) {
			return;
		}

		try {
			const response = await fetch(`${databaseManager.getApiUrl()}/api/admin/posts/${postId}/delete`, {
				method: 'POST',
				headers: databaseManager.getHeaders()
			});

			if (response.ok) {
				await loadAllData(); // Refresh the list
			} else {
				const errorData = await response.json();
				alert('Failed to delete post: ' + errorData.detail);
			}
		} catch (err) {
			console.error('Delete failed:', err);
			alert('Failed to delete post. Please try again.');
		}
	}

	async function restorePost(postId: number) {
		try {
			const response = await fetch(`${databaseManager.getApiUrl()}/api/admin/posts/${postId}/restore`, {
				method: 'POST',
				headers: databaseManager.getHeaders()
			});

			if (response.ok) {
				await loadAllData(); // Refresh the list
			} else {
				const errorData = await response.json();
				alert('Failed to restore post: ' + errorData.detail);
			}
		} catch (err) {
			console.error('Restore failed:', err);
			alert('Failed to restore post. Please try again.');
		}
	}

	async function reprocessPost(post: PostListItem) {
		if (!confirm('Reprocess this post? This will regenerate the AI comments.')) {
			return;
		}

		submitting = true;
		try {
			const response = await fetch(`${databaseManager.getApiUrl()}/api/posts/submit`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					...databaseManager.getHeaders()
				},
				body: JSON.stringify({
					url: post.reddit_url,
					overwrite_existing: true
				})
			});

			if (response.ok) {
				await loadAllData(); // Refresh the list
				closeDropdown();
			} else {
				const errorData = await response.json();
				alert('Failed to reprocess post: ' + errorData.detail);
			}
		} catch (err) {
			console.error('Reprocess failed:', err);
			alert('Failed to reprocess post. Please try again.');
		} finally {
			submitting = false;
		}
	}

	function toggleDropdown(postId: number) {
		openDropdownId = openDropdownId === postId ? null : postId;
	}

	function closeDropdown() {
		openDropdownId = null;
	}

	// Get display name for subreddit
	function getSubredditDisplayName(subreddit: string): string {
		const displayMap: Record<string, string> = {
			'unpopularopinion': 'r/unpopularopinion',
			'AmItheAsshole': 'r/AmItheAsshole', 
			'relationship_advice': 'r/relationship_advice'
		};
		return displayMap[subreddit] || `r/${subreddit}`;
	}
</script>

<svelte:head>
	<title>{getSubredditDisplayName(currentSubreddit)} - Reddit or Replicant</title>
</svelte:head>

<div class="min-h-screen text-gray-100 relative z-10">
	<!-- Fixed Toolbar -->
	<div class="fixed top-0 left-0 right-0 z-50 border-b border-gray-700" style="background: rgba(17, 17, 20, 0.95); backdrop-filter: blur(10px);">
		<div class="max-w-4xl mx-auto px-4 md:px-0 py-3">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-4">
					<a href="/subreddit" class="transition-colors flex items-center gap-1" style="color: #00d4ff;" >
						← Back
					</a>
					<a href="/" class="text-lg font-bold cursor-pointer hover:text-blue-300 transition-colors hidden sm:block" style="color: #f3f4f6; text-shadow: 0 0 8px rgba(0, 212, 255, 0.1);">
						Reddit or <span class="glitch" data-text="Replicant">Replicant</span>?
					</a>
				</div>
				<div class="flex items-center gap-4">
					<a href="/about" class="transition-colors text-sm" style="color: #00d4ff;" >
						About
					</a>
					<DatabaseSelector on:change={loadAllData} />
				</div>
			</div>
		</div>
	</div>

	<!-- Content with top padding to account for fixed toolbar -->
	<div class="pt-16">
	<div class="container mx-auto p-8 md:px-0">

		<!-- Header with Add Button (always visible for admins) -->
		{#if !loading}
			<div class="max-w-4xl mx-auto">
				<!-- Desktop Layout -->
				<div class="hidden sm:flex justify-between items-center mb-6">
					<h2 class="text-xl font-semibold text-white">
						{#if posts.length > 0}
							Replicants are hiding in {getSubredditDisplayName(currentSubreddit)}
						{:else}
							{getSubredditDisplayName(currentSubreddit)}
						{/if}
					</h2>
					{#if showAdminFeatures}
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

				<!-- Mobile Layout -->
				<div class="sm:hidden mb-6">
					<h2 class="text-xl font-semibold text-white mb-4">
						{#if posts.length > 0}
							Replicants arehiding in {getSubredditDisplayName(currentSubreddit)}
						{:else}
							{getSubredditDisplayName(currentSubreddit)}
						{/if}
					</h2>
					{#if showAdminFeatures}
						<button
							on:click={openDialog}
							class="w-full px-4 py-2 text-white rounded transition-all duration-200 cursor-pointer hover:scale-105"
							style="background: linear-gradient(135deg, var(--replicant-primary), var(--replicant-secondary)); border: 1px solid var(--replicant-border);"
							on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px var(--replicant-glow)'}
							on:mouseleave={(e) => e.target.style.boxShadow = ''}
						>
							+ Add New Post
						</button>
					{/if}
				</div>
			</div>
		{/if}

		<!-- Posts List -->
		{#if loading}
			<div class="text-center">
				<div class="animate-pulse text-gray-300">Loading posts...</div>
			</div>
		{:else if posts.length > 0}
			<div class="max-w-4xl mx-auto">
				<div class="grid gap-4">
					{#each posts as post}
						{@const progressStatus = getProgressStatus(post.id, post.total_count)}
						{@const userPostProgress = userProgress[post.id]}
						<div
							class="border border-gray-700 rounded-lg p-6 transition-all duration-200"
							class:opacity-50={post.is_deleted}
							class:hover:border-blue-400={!post.is_deleted}
							class:hover:border-amber-400={post.is_deleted}
							class:cursor-pointer={!post.is_deleted}
							class:hover:scale-[1.02]={!post.is_deleted}
							style="background: rgba(17, 17, 20, 0.85); backdrop-filter: blur(10px);"
							on:click={() => !post.is_deleted && playGame(post.id)}
							on:keydown={(e) => e.key === 'Enter' && !post.is_deleted && playGame(post.id)}
							role={!post.is_deleted ? "button" : ""}
							tabindex={!post.is_deleted ? 0 : -1}
						>
							<!-- Desktop Layout -->
							<div class="hidden sm:flex justify-between items-start">
								<div class="flex-1">
									<div class="flex items-center gap-2 mb-2">
										<h3 class="font-medium text-white text-lg">{post.title}</h3>
										{#if post.is_deleted}
											<span class="px-2 py-1 text-xs rounded text-amber-200 bg-amber-900/30 border border-amber-700/50">
												Deleted
											</span>
										{/if}
									</div>
									<div class="text-sm text-gray-400 mb-2">
										<span style="color: #00d4ff;">r/{post.subreddit}</span>
										• {post.total_count} comments
									</div>
									{#if showAdminFeatures}
										<div class="text-xs text-gray-500">
											Added {new Date(post.created_at).toLocaleDateString()}
											{#if post.is_deleted && post.deleted_at}
												• Deleted {new Date(post.deleted_at).toLocaleDateString()}
											{/if}
										</div>
									{/if}
								</div>
								<div class="ml-4 flex flex-col items-end">
									<div class="flex {showAdminFeatures ? 'gap-2' : 'flex-col'} items-end {showAdminFeatures ? 'mb-1' : 'mb-2'}">
										{#if !post.is_deleted}
											<button
												class="px-3 py-1 text-white rounded text-sm transition-all duration-200 hover:scale-105 cursor-pointer"
												style="background: linear-gradient(135deg, var(--replicant-primary), var(--replicant-secondary)); border: 1px solid var(--replicant-border);"
												on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px var(--replicant-glow)'}
												on:mouseleave={(e) => e.target.style.boxShadow = ''}
												on:click|stopPropagation={() => playGame(post.id)}
											>
												{#if progressStatus === 'completed'}
													Review ({Math.round(userPostProgress.accuracy * 100)}% accuracy)
												{:else if progressStatus === 'in-progress'}
													Continue
												{:else}
													Begin Test
												{/if}
											</button>
											{#if showAdminFeatures}
												<div class="relative">
													<button
														on:click|stopPropagation={() => toggleDropdown(post.id)}
														class="px-2 py-1 text-gray-400 hover:text-white rounded text-sm transition-all duration-200 hover:bg-gray-700"
														title="Post options"
													>
														⋮
													</button>
													{#if openDropdownId === post.id}
														<div
															class="absolute right-0 top-8 z-10 bg-gray-800 border border-gray-600 rounded-lg shadow-lg py-1 min-w-[120px]"
															on:click|stopPropagation={() => {}}
														>
															<button
																on:click|stopPropagation={() => reprocessPost(post)}
																class="w-full px-3 py-2 text-left text-white hover:bg-gray-700 transition-colors text-sm"
																disabled={submitting}
															>
																{submitting ? 'Processing...' : 'Reprocess'}
															</button>
															<button
																on:click|stopPropagation={() => { deletePost(post.id); closeDropdown(); }}
																class="w-full px-3 py-2 text-left text-red-400 hover:bg-gray-700 transition-colors text-sm"
															>
																Delete
															</button>
														</div>
													{/if}
												</div>
											{/if}
										{:else if showAdminFeatures}
											<button
												on:click|stopPropagation={() => restorePost(post.id)}
												class="px-3 py-1 text-white rounded text-sm transition-all duration-200 hover:scale-105 cursor-pointer"
												style="background: linear-gradient(135deg, #166534, #16a34a); border: 1px solid rgba(34, 197, 94, 0.3);"
												on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px rgba(34, 197, 94, 0.4)'}
												on:mouseleave={(e) => e.target.style.boxShadow = ''}
											>
												Restore
											</button>
										{/if}
									</div>
									{#if userPostProgress && userPostProgress.total_guesses > 0}
										<div class="text-xs text-gray-400">
											{userPostProgress.total_guesses} guessed ({userPostProgress.correct_guesses} correct)
										</div>
									{/if}
								</div>
							</div>

							<!-- Mobile Layout -->
							<div class="sm:hidden">
								<!-- Title spans full width -->
								<div class="flex items-center gap-2 mb-3">
									<h3 class="font-medium text-white text-lg">{post.title}</h3>
									{#if post.is_deleted}
										<span class="px-2 py-1 text-xs rounded text-amber-200 bg-amber-900/30 border border-amber-700/50">
											Deleted
										</span>
									{/if}
								</div>

								<!-- Subreddit info and buttons on same line -->
								<div class="flex justify-between items-center">
									<div>
										<div class="text-sm text-gray-400 mb-1">
											<div><span style="color: #00d4ff;">r/{post.subreddit}</span></div>
											<div>{post.total_count} comments</div>
										</div>
										{#if userPostProgress && userPostProgress.total_guesses > 0}
											<div class="text-xs text-gray-400">
												{userPostProgress.total_guesses} guessed ({userPostProgress.correct_guesses} correct)
											</div>
										{/if}
										{#if showAdminFeatures}
											<div class="text-xs text-gray-500">
												Added {new Date(post.created_at).toLocaleDateString()}
												{#if post.is_deleted && post.deleted_at}
													• Deleted {new Date(post.deleted_at).toLocaleDateString()}
												{/if}
											</div>
										{/if}
									</div>

									<div class="flex flex-col gap-2 items-end ml-4">
										{#if !post.is_deleted}
											<button
												class="px-3 py-1 text-white rounded text-sm transition-all duration-200 hover:scale-105 cursor-pointer"
												style="background: linear-gradient(135deg, var(--replicant-primary), var(--replicant-secondary)); border: 1px solid var(--replicant-border);"
												on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px var(--replicant-glow)'}
												on:mouseleave={(e) => e.target.style.boxShadow = ''}
												on:click|stopPropagation={() => playGame(post.id)}
											>
												{#if progressStatus === 'completed'}
													Review ({Math.round(userPostProgress.accuracy * 100)}% accuracy)
												{:else if progressStatus === 'in-progress'}
													Continue
												{:else}
													Begin Test
												{/if}
											</button>
											{#if showAdminFeatures}
												<div class="relative">
													<button
														on:click|stopPropagation={() => toggleDropdown(post.id)}
														class="px-2 py-1 text-gray-400 hover:text-white rounded text-sm transition-all duration-200 hover:bg-gray-700"
														title="Post options"
													>
														⋮
													</button>
													{#if openDropdownId === post.id}
														<div
															class="absolute right-0 top-8 z-10 bg-gray-800 border border-gray-600 rounded-lg shadow-lg py-1 min-w-[120px]"
															on:click|stopPropagation={() => {}}
														>
															<button
																on:click|stopPropagation={() => reprocessPost(post)}
																class="w-full px-3 py-2 text-left text-white hover:bg-gray-700 transition-colors text-sm"
																disabled={submitting}
															>
																{submitting ? 'Processing...' : 'Reprocess'}
															</button>
															<button
																on:click|stopPropagation={() => { deletePost(post.id); closeDropdown(); }}
																class="w-full px-3 py-2 text-left text-red-400 hover:bg-gray-700 transition-colors text-sm"
															>
																Delete
															</button>
														</div>
													{/if}
												</div>
											{/if}
										{:else if showAdminFeatures}
											<button
												on:click|stopPropagation={() => restorePost(post.id)}
												class="px-3 py-1 text-white rounded text-sm transition-all duration-200 hover:scale-105 cursor-pointer"
												style="background: linear-gradient(135deg, #166534, #16a34a); border: 1px solid rgba(34, 197, 94, 0.3);"
												on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px rgba(34, 197, 94, 0.4)'}
												on:mouseleave={(e) => e.target.style.boxShadow = ''}
											>
												Restore
											</button>
										{/if}
									</div>
								</div>
							</div>
						</div>
					{/each}
				</div>
			</div>
		{:else}
			<div class="text-center text-gray-400 max-w-2xl mx-auto">
				<h3 class="text-lg font-medium mb-4 text-white">
					No posts found
				</h3>
				<p class="mb-6">
					There are currently no posts available for this subreddit.
					{#if showAdminFeatures}
						Click "Add New Post" above to submit a Reddit URL, or try a different community.
					{:else}
						Check back later or try a different community.
					{/if}
				</p>
				<a
					href="/subreddit"
					class="px-6 py-3 text-white rounded transition-all duration-200 cursor-pointer hover:scale-105 inline-block"
					style="background: linear-gradient(135deg, var(--replicant-primary), var(--replicant-secondary)); border: 1px solid var(--replicant-border);"
					on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px var(--replicant-glow)'}
					on:mouseleave={(e) => e.target.style.boxShadow = ''}
				>
					← Choose Different Community
				</a>
			</div>
		{/if}
	</div>
	</div>
</div>

<!-- Submit Dialog (Admin only) -->
{#if showSubmitDialog && showAdminFeatures}
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

			<div class="mt-3">
				<label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
					<input
						type="checkbox"
						bind:checked={overwriteExisting}
						class="rounded bg-gray-800 border-gray-600 text-blue-500 focus:ring-blue-500 focus:ring-2"
						disabled={submitting}
					/>
					Overwrite existing post (if URL already processed)
				</label>
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