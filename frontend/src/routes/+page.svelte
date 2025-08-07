<script lang="ts">
	import { onMount } from 'svelte';

	interface Post {
		id: string;
		title: string;
		content: string;
		author: string;
		subreddit: string;
		score: number;
		comment_count: number;
	}

	interface Comment {
		id: string;
		author: string;
		content: string;
		content_html: string | null;
		score: number;
		depth: number;
		parent_id: string | null;
		replies: Comment[];
		is_ai: boolean;
	}

	interface RedditData {
		post: Post;
		comments: Comment[];
	}

	let redditData: RedditData | null = null;
	let loading = true;
	let error = '';

	onMount(async () => {
		try {
			const response = await fetch('/api/mixed-comments');
			if (!response.ok) throw new Error('Failed to fetch');
			const data = await response.json();
			
			if (data.error) {
				error = data.error;
			} else {
				redditData = data;
			}
		} catch (err) {
			error = 'Failed to load Reddit data';
			console.error(err);
		} finally {
			loading = false;
		}
	});

	// Track guessing state for each comment
	let guessedComments = new Map<string, { guessed: boolean; correct: boolean; userGuess: 'reddit' | 'replicant' }>();

	function getAllComments(comment: Comment, allComments: Comment[] = []): Comment[] {
		allComments.push(comment);
		if (comment.replies && comment.replies.length > 0) {
			comment.replies.forEach((reply: Comment) => {
				getAllComments(reply, allComments);
			});
		}
		return allComments;
	}

	function makeGuess(commentId: string, guess: 'reddit' | 'replicant', actualIsAi: boolean) {
		const correct = (guess === 'replicant' && actualIsAi) || (guess === 'reddit' && !actualIsAi);
		
		guessedComments.set(commentId, {
			guessed: true,
			correct: correct,
			userGuess: guess
		});
		
		// Trigger reactivity
		guessedComments = guessedComments;
	}
</script>

<div class="min-h-screen text-gray-100" style="background: linear-gradient(180deg, #0a0a0b 0%, #111013 100%)">
	{#if loading}
		<div class="p-8">
			<div class="animate-pulse text-gray-300">Loading Reddit data...</div>
		</div>
	{:else if error}
		<div class="p-8 text-red-400">
			{error}
		</div>
	{:else if redditData}
		<div class="max-w-4xl mx-auto" style="background: rgba(17, 17, 20, 0.85); backdrop-filter: blur(10px); border: 1px solid rgba(55, 65, 81, 0.3); box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);">
			<!-- Post -->
			{#if redditData.post}
				<div class="border-b border-gray-700 p-6">
					<div class="mb-4">
						<span class="text-sm" style="color: #00d4ff; text-shadow: 0 0 8px rgba(0, 212, 255, 0.3);">r/{redditData.post.subreddit}</span>
						<span class="text-sm text-gray-400 ml-2">• Posted by u/{redditData.post.author}</span>
					</div>
					<h1 class="text-2xl font-bold mb-4" style="color: #f3f4f6; text-shadow: 0 0 12px rgba(0, 212, 255, 0.1);">{redditData.post.title}</h1>
					{#if redditData.post.content}
						<div class="text-gray-200 mb-4 whitespace-pre-wrap content-text">{redditData.post.content}</div>
					{/if}
					<div class="text-sm text-gray-400">
						{redditData.post.score} points • {redditData.post.comment_count} comments
					</div>
				</div>
			{/if}

			<!-- Comments -->
			{#if redditData.comments && redditData.comments.length > 0}
				<div class="p-6">
					<h2 class="text-lg font-semibold mb-4 text-white">Comments</h2>
					{#each redditData.comments as comment}
						{@const allComments = getAllComments(comment)}
						{#each allComments as flatComment}
							{@const guessState = guessedComments.get(flatComment.id)}
							<div class="comment mb-3 p-3 rounded-lg transition-colors" 
								 class:bg-gray-750={!guessState?.guessed}
								 class:bg-green-900={guessState?.guessed && guessState?.correct}
								 class:bg-red-900={guessState?.guessed && !guessState?.correct}
								 style="margin-left: {flatComment.depth * 20}px">
								<div class="border-l-2 pl-3" style="border-color: rgba(75, 85, 99, 0.4);">
									<div class="text-sm text-gray-400 mb-2">
										<span class="font-medium" style="color: #00d4ff; text-shadow: 0 0 8px rgba(0, 212, 255, 0.2);">u/{flatComment.author}</span>
										<span class="ml-2">{flatComment.score} points</span>
									</div>
									
									{#if flatComment.content_html}
										<div class="mb-3 prose prose-invert prose-sm max-w-none text-gray-200 content-text">
											{@html flatComment.content_html}
										</div>
									{:else}
										<div class="mb-3 whitespace-pre-wrap text-gray-200 content-text">
											{flatComment.content}
										</div>
									{/if}

									<!-- Guessing Interface -->
									<div class="pt-2" style="border-top: 1px solid rgba(75, 85, 99, 0.3);">
										{#if !guessState?.guessed}
											<div class="flex gap-3 items-center">
												<span class="text-xs text-gray-400">Origin:</span>
												<button 
													class="px-2 py-1 text-white rounded text-xs transition-all duration-200 hover:scale-105 hover:shadow-lg cursor-pointer"
													style="background: linear-gradient(135deg, #1e3a8a, #3b82f6); border: 1px solid rgba(0, 212, 255, 0.3);"
													on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px rgba(0, 212, 255, 0.4)'}
													on:mouseleave={(e) => e.target.style.boxShadow = ''}
													on:click={() => makeGuess(flatComment.id, 'reddit', flatComment.is_ai)}
												>
													Reddit
												</button>
												<button 
													class="px-2 py-1 text-white rounded text-xs transition-all duration-200 hover:scale-105 hover:shadow-lg cursor-pointer"
													style="background: linear-gradient(135deg, #7f1d1d, #dc2626); border: 1px solid rgba(255, 69, 0, 0.3);"
													on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px rgba(255, 69, 0, 0.4)'}
													on:mouseleave={(e) => e.target.style.boxShadow = ''}
													on:click={() => makeGuess(flatComment.id, 'replicant', flatComment.is_ai)}
												>
													Replicant
												</button>
											</div>
										{:else}
											<div class="space-y-1">
												<div class="flex gap-3 items-center">
													<span class="text-xs text-gray-400">Origin:</span>
													<button 
														class="px-2 py-1 rounded text-xs cursor-not-allowed"
														class:bg-green-600={guessState.userGuess === 'reddit' && !flatComment.is_ai}
														class:bg-red-600={guessState.userGuess === 'reddit' && flatComment.is_ai}
														class:bg-gray-600={guessState.userGuess !== 'reddit'}
														class:text-white={guessState.userGuess === 'reddit'}
														class:text-gray-400={guessState.userGuess !== 'reddit'}
														disabled
													>
														Reddit {guessState.userGuess === 'reddit' ? '✓' : ''}
													</button>
													<button 
														class="px-2 py-1 rounded text-xs cursor-not-allowed"
														class:bg-green-600={guessState.userGuess === 'replicant' && flatComment.is_ai}
														class:bg-red-600={guessState.userGuess === 'replicant' && !flatComment.is_ai}
														class:bg-gray-600={guessState.userGuess !== 'replicant'}
														class:text-white={guessState.userGuess === 'replicant'}
														class:text-gray-400={guessState.userGuess !== 'replicant'}
														disabled
													>
														Replicant {guessState.userGuess === 'replicant' ? '✓' : ''}
													</button>
												</div>
												<div class="text-xs">
													{#if guessState.correct}
														<span class="text-green-400">✅ Correct! This was {flatComment.is_ai ? 'a replicant' : 'from Reddit'}.</span>
													{:else}
														<span class="text-red-400">❌ Wrong! This was actually {flatComment.is_ai ? 'a replicant' : 'from Reddit'}.</span>
													{/if}
												</div>
											</div>
										{/if}
									</div>
								</div>
							</div>
						{/each}
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>
