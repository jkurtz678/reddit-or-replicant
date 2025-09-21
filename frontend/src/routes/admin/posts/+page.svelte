<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { adminSession } from '$lib/admin';

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

	let posts: PostListItem[] = [];
	let loading = true;
	let submitting = false;
	let error = '';
	let redditUrl = '';
	let showSubmitDialog = false;
	let dialogVisible = false;

	// Check admin auth on mount
	onMount(async () => {
		if (!adminSession.isAdmin()) {
			goto('/admin');
			return;
		}
		await loadPosts();
	});

	// Handle dialog opening with transition
	function openDialog() {
		showSubmitDialog = true;
		setTimeout(() => dialogVisible = true, 10);
	}

	// Handle dialog closing with transition  
	function closeDialog() {
		dialogVisible = false;
		setTimeout(() => showSubmitDialog = false, 300);
	}

	async function loadPosts() {
		try {
			loading = true;
			const response = await fetch('/api/posts?include_deleted=true');
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
			
			// Clear input, close dialog, and reload posts
			redditUrl = '';
			closeDialog();
			await loadPosts();
			
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
			const response = await fetch(`/api/admin/posts/${postId}/delete`, {
				method: 'POST'
			});

			if (response.ok) {
				await loadPosts(); // Refresh the list
			} else {
				const errorData = await response.json();
				alert(`Failed to delete post: ${errorData.detail}`);
			}
		} catch (err) {
			console.error('Delete failed:', err);
			alert('Failed to delete post. Please try again.');
		}
	}

	async function restorePost(postId: number) {
		try {
			const response = await fetch(`/api/admin/posts/${postId}/restore`, {
				method: 'POST'
			});

			if (response.ok) {
				await loadPosts(); // Refresh the list
			} else {
				const errorData = await response.json();
				alert(`Failed to restore post: ${errorData.detail}`);
			}
		} catch (err) {
			console.error('Restore failed:', err);
			alert('Failed to restore post. Please try again.');
		}
	}

	function logout() {
		adminSession.logout();
		goto('/');
	}
</script>

<div class="min-h-screen text-gray-100" style="background: linear-gradient(180deg, #0a0a0b 0%, #111013 100%)">
	<!-- Fixed Toolbar -->
	<div class="fixed top-0 left-0 right-0 z-50 border-b border-gray-700" style="background: rgba(17, 17, 20, 0.95); backdrop-filter: blur(10px);">
		<div class="max-w-4xl mx-auto px-4 py-3">
			<div class="flex items-center justify-between">
				<a href="/" class="text-lg font-bold cursor-pointer hover:text-blue-300 transition-colors" style="color: #f3f4f6; text-shadow: 0 0 8px rgba(0, 212, 255, 0.1);">
					Reddit or <span class="glitch" data-text="Replicant">Replicant</span>?
				</a>
				<div class="flex items-center gap-4">
					<span class="text-sm text-amber-400">Admin Mode</span>
					<button 
						on:click={logout}
						class="px-3 py-1 text-white rounded text-sm transition-all duration-200 cursor-pointer hover:scale-105"
						style="background: linear-gradient(135deg, #374151, #6b7280); border: 1px solid rgba(156, 163, 175, 0.3);"
					>
						Logout
					</button>
				</div>
			</div>
		</div>
	</div>

	<!-- Content with top padding to account for fixed toolbar -->
	<div class="pt-16">
	<div class="container mx-auto p-8">

		<!-- Posts List -->
		{#if loading}
			<div class="text-center">
				<div class="animate-pulse text-gray-300">Loading posts...</div>
			</div>
		{:else if posts.length > 0}
			<div class="max-w-4xl mx-auto">
				<div class="flex justify-between items-center mb-6">
					<h2 class="text-xl font-semibold text-white">Manage Posts</h2>
					<button 
						on:click={openDialog}
						class="px-4 py-2 text-white rounded transition-all duration-200 cursor-pointer hover:scale-105"
						style="background: linear-gradient(135deg, var(--replicant-primary), var(--replicant-secondary)); border: 1px solid var(--replicant-border);"
						on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px var(--replicant-glow)'}
						on:mouseleave={(e) => e.target.style.boxShadow = ''}
					>
						+ Add New Post
					</button>
				</div>
				<div class="grid gap-4">
					{#each posts as post}
						<div 
							class="border border-gray-700 rounded-lg p-6 transition-all duration-200"
							class:opacity-50={post.is_deleted}
							class:hover:border-blue-400={!post.is_deleted}
							class:hover:border-amber-400={post.is_deleted}
							style="background: rgba(17, 17, 20, 0.85); backdrop-filter: blur(10px);"
						>
							<div class="flex justify-between items-center mb-3">
								<div class="flex-1">
									<div class="flex items-center gap-2 mb-2">
										<h3 class="font-medium text-white text-lg">{post.title}</h3>
									</div>
									<div class="text-sm text-gray-400 mb-2">
										<span style="color: #00d4ff;">r/{post.subreddit}</span>
										• {post.total_count} comments ({post.ai_count} AI, {post.total_count - post.ai_count} real)
										• {Math.round((post.ai_count / post.total_count) * 100)}% AI
									</div>
									<div class="text-xs text-gray-500">
										Added {new Date(post.created_at).toLocaleDateString()}
										{#if post.is_deleted && post.deleted_at}
											• Deleted {new Date(post.deleted_at).toLocaleDateString()}
										{/if}
									</div>
								</div>
								<div class="ml-4 flex gap-2 items-center">
									{#if !post.is_deleted}
										<button 
											on:click={() => playGame(post.id)}
											class="px-3 py-1 text-white rounded text-sm transition-all duration-200 hover:scale-105 cursor-pointer"
											style="background: linear-gradient(135deg, var(--replicant-primary), var(--replicant-secondary)); border: 1px solid var(--replicant-border);"
											on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px var(--replicant-glow)'}
											on:mouseleave={(e) => e.target.style.boxShadow = ''}
										>
											Begin Test
										</button>
										<button 
											on:click={() => deletePost(post.id)}
											class="px-3 py-1 text-white rounded text-sm transition-all duration-200 hover:scale-105 cursor-pointer"
											style="background: linear-gradient(135deg, #7f1d1d, #dc2626); border: 1px solid rgba(220, 38, 38, 0.3);"
											on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px rgba(220, 38, 38, 0.4)'}
											on:mouseleave={(e) => e.target.style.boxShadow = ''}
										>
											Delete
										</button>
									{:else}
										<span class="px-2 py-1 text-xs rounded text-amber-200 bg-amber-900/30 border border-amber-700/50">
											Deleted
										</span>
										<button 
											on:click={() => restorePost(post.id)}
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
					{/each}
				</div>
			</div>
		{:else}
			<div class="text-center text-gray-400">
				<p class="mb-4">No posts yet. Add your first Reddit post!</p>
				<button 
					on:click={openDialog}
					class="px-6 py-3 text-white rounded transition-all duration-200 cursor-pointer hover:scale-105"
					style="background: linear-gradient(135deg, var(--replicant-primary), var(--replicant-secondary)); border: 1px solid var(--replicant-border);"
					on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px var(--replicant-glow)'}
					on:mouseleave={(e) => e.target.style.boxShadow = ''}
				>
					+ Add Your First Post
				</button>
			</div>
		{/if}
	</div>
	</div>
</div>

<!-- Submit Dialog -->
{#if showSubmitDialog}
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
					{submitting ? 'Processing...' : 'Submit'}
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