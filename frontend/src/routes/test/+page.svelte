<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import { fade } from 'svelte/transition';
	import { userManager } from '$lib/user';
	import { browser } from '$app/environment';
	import { databaseManager, isLocalEnvironment } from '$lib/environment';

	// Glitch character pool - only ASCII characters that are truly monospace
	const glitchChars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}|\\;:,.<>?/~`';
	
	// Store original comment text and glitch intervals
	let originalTexts = new Map();
	let glitchIntervals = new Map();

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
		generation_prompt?: string;
		archetype_used?: string;
	}

	interface RedditData {
		post: Post;
		comments: Comment[];
	}

	let redditData: RedditData | null = null;
	let loading = true;
	let error = '';
	let currentPostId: number | null = null;
	let anonymousUserId: string = '';
	let progressLoaded = false;
	let currentSubreddit: string = '';
	let showResultsDialog = false;
	let resultsDialogVisible = false;
	let resultsShown = false;
	let justMadeGuess = false;
	let showFeedbackDialog = false;
	let feedbackDialogVisible = false;
	let feedbackCommentId = '';
	let feedbackCommentContent = '';
	let feedbackSubmitting = false;
	let flaggedComments = new Set();
	let postExpanded = false;
	let showPromptDialog = false;
	let promptDialogComment: Comment | null = null;
	let jsonCopied = false;
	let tyrellAgenda: string | null = null;

	// Initialize user ID when in browser
	$: if (browser && !anonymousUserId) {
		anonymousUserId = userManager.getUserId();
	}
	
	// Load all data when both post ID and user are available
	$: if (browser && anonymousUserId && currentPostId && !progressLoaded) {
		loadAllData();
	}
	
	// Initialize post ID from URL params
	onMount(async () => {
		const postId = $page.url.searchParams.get('post');

		if (postId) {
			currentPostId = parseInt(postId);
			// The reactive statement will handle loading when anonymousUserId is available
		} else {
			loading = false;
			error = 'No post specified. Visit /subreddit to choose a community.';
		}
	});

	async function loadPost(postId: number) {
		try {
			const response = await fetch(`${databaseManager.getApiUrl()}/api/mixed-comments/${postId}`, {
				headers: databaseManager.getHeaders()
			});
			if (!response.ok) {
				if (response.status === 404) {
					throw new Error('Post not found');
				}
				throw new Error('Failed to fetch post data');
			}
			const data = await response.json();
			return data;

		} catch (err: any) {
			console.error('Error loading post:', err);
			throw err;
		}
	}

	async function loadUserProgress() {
		if (!browser || !currentPostId || !anonymousUserId) return null;

		try {
			const response = await fetch(`${databaseManager.getApiUrl()}/api/users/progress`, {
				method: 'POST',
				headers: databaseManager.getHeaders(),
				body: JSON.stringify({
					anonymous_id: anonymousUserId,
					post_id: currentPostId
				})
			});

			if (!response.ok) {
				throw new Error('Failed to load user progress');
			}

			const progress = await response.json();
			return progress;

		} catch (err) {
			console.error('Error loading user progress:', err);
			throw err;
		}
	}

	async function loadAllData() {
		if (!browser || !currentPostId || !anonymousUserId) return;

		try {
			loading = true;
			error = '';

			// Run both API calls in parallel
			const [postData, progressData] = await Promise.all([
				loadPost(currentPostId),
				loadUserProgress()
			]);

			// Update state only after both complete successfully
			redditData = postData;
			currentSubreddit = postData.post?.subreddit || '';
			tyrellAgenda = postData.tyrell_agenda || null;

			// Reset guessing state (will be restored from backend if exists)
			guessedComments = new Map();

			// Reset post expansion state
			postExpanded = false;

			// Restore guessing state from backend if progress exists
			if (progressData && progressData.guesses && progressData.guesses.length > 0) {
				for (const guess of progressData.guesses) {
					guessedComments.set(guess.comment_id, {
						guessed: true,
						correct: guess.is_correct,
						userGuess: guess.guess as 'reddit' | 'replicant'
					});

					// Restore flagged state
					if (guess.flagged_as_obvious) {
						flaggedComments.add(guess.comment_id);
					}

					// Restart text glitching for AI comments that were already guessed
					const comment = getAllCommentsFlat(postData.comments).find(c => c.id === guess.comment_id);
					if (comment && comment.is_ai) {
						setTimeout(() => startTextGlitch(guess.comment_id, comment.content), 100);
					}
				}

				// Trigger reactivity
				guessedComments = guessedComments;
				flaggedComments = flaggedComments;
			}

			progressLoaded = true;

		} catch (err: any) {
			error = err.message || 'Failed to load data';
			console.error('Error loading data:', err);
			// Reset state on error
			redditData = null;
			guessedComments = new Map();
			progressLoaded = false;
		} finally {
			loading = false;
		}
	}

	async function resetProgress() {
		if (!browser || !currentPostId || !anonymousUserId) return;
		
		if (!confirm('Are you sure you want to reset your progress on this post? This will clear all your guesses.')) {
			return;
		}
		
		try {
			const response = await fetch(`${databaseManager.getApiUrl()}/api/users/reset-progress`, {
				method: 'POST',
				headers: databaseManager.getHeaders(),
				body: JSON.stringify({
					anonymous_id: anonymousUserId,
					post_id: currentPostId
				})
			});
			
			if (!response.ok) {
				throw new Error('Failed to reset progress');
			}
			
			// Clear local state
			guessedComments.clear();
			guessedComments = guessedComments;
			flaggedComments.clear();
			flaggedComments = flaggedComments;
			progressLoaded = false; // Allow progress to be reloaded
			resultsShown = false; // Allow results to show again after reset
			justMadeGuess = false; // Reset guess flag
			
			// Stop all text glitching
			glitchIntervals.forEach(timeout => clearTimeout(timeout));
			glitchIntervals.clear();
			originalTexts.clear();
			
			// Reset all glitch effects in DOM
			const allGlitchTexts = document.querySelectorAll('.glitch-text');
			allGlitchTexts.forEach(element => {
				element.classList.remove('glitching', 'glitch');
			});
			
			alert('Progress reset successfully!');
			
		} catch (err) {
			console.error('Error resetting progress:', err);
			alert('Failed to reset progress. Please try again.');
		}
	}
	
	// Get result message based on accuracy
	function getResultMessage(accuracy: number): string {
		if (accuracy >= 0.9) {
			return "Exceptional performance. Your detection skills are highly refined - you've identified the vast majority of replicants while avoiding false positives.";
		} else if (accuracy >= 0.8) {
			return "Impressive performance. You've shown remarkable ability to distinguish replicants from humans, but some still slip through undetected.";
		} else if (accuracy >= 0.7) {
			return "Adequate detection rate. Your instincts serve you well, though several replicants have successfully mimicked human discourse.";
		} else if (accuracy >= 0.6) {
			return "Concerning results. The replicants are evolving faster than our ability to detect them. More training is required.";
		} else if (accuracy >= 0.5) {
			return "Barely better than random chance. The replicants have learned to perfectly imitate human communication patterns. We may already be outnumbered.";
		} else {
			return "Critical failure. Your inability to distinguish humans from replicants poses a significant threat to the mission. Immediate recalibration recommended.";
		}
	}
	
	// Close results dialog
	function closeResultsDialog() {
		resultsDialogVisible = false;
		setTimeout(() => showResultsDialog = false, 300);
	}
	
	// Show results dialog manually
	function showResults() {
		showResultsDialog = true;
		setTimeout(() => resultsDialogVisible = true, 10);
	}

	// Track guessing state for each comment
	let guessedComments = new Map<string, { guessed: boolean; correct: boolean; userGuess: 'reddit' | 'replicant' }>();

	// Calculate stats for toolbar
	$: totalComments = redditData ? getAllCommentsFlat(redditData.comments).length : 0;
	$: guessedArray = Array.from(guessedComments.values());
	$: correctGuesses = guessedArray.filter(g => g.correct).length;
	$: incorrectGuesses = guessedArray.filter(g => !g.correct).length;
	$: totalGuessed = guessedArray.length;
	$: remainingGuesses = totalComments - totalGuessed;
	$: accuracy = totalGuessed > 0 ? (correctGuesses / totalGuessed) : 0;
	
	// Check if all comments have been guessed and show results (only if just made a guess)
	$: if (totalComments > 0 && remainingGuesses === 0 && totalGuessed > 0 && !resultsShown && justMadeGuess) {
		// Wait 1 second before showing results
		setTimeout(() => {
			showResultsDialog = true;
			setTimeout(() => resultsDialogVisible = true, 10);
			justMadeGuess = false; // Reset the flag after showing
		}, 1000);
		resultsShown = true;
	}

	function getAllCommentsFlat(comments: Comment[]): Comment[] {
		const flat: Comment[] = [];
		for (const comment of comments) {
			flat.push(comment);
			flat.push(...getAllCommentsFlat(comment.replies));
		}
		return flat;
	}

	function getAllComments(comment: Comment, allComments: Comment[] = []): Comment[] {
		allComments.push(comment);
		if (comment.replies && comment.replies.length > 0) {
			comment.replies.forEach((reply: Comment) => {
				getAllComments(reply, allComments);
			});
		}
		return allComments;
	}

	function startTextGlitch(commentId: string, originalText: string) {
		// Store original text
		originalTexts.set(commentId, originalText);
		
		const element = document.querySelector(`[data-comment-id="${commentId}"] .glitch-text`);
		if (!element) return;
		
		// Step 1: Fade out with transitioning class
		element.classList.add('transitioning');
		
		// Step 2: After fade out, switch to monospace and apply both glitch classes
		setTimeout(() => {
			element.classList.add('glitching');
			element.classList.add('glitch');
			element.classList.remove('transitioning');
			
			// Step 3: Start glitching after fade back in with random timing
			setTimeout(() => {
				function scheduleNextGlitch() {
					const text = originalTexts.get(commentId) || originalText;
					const textArray = text.split('');
					
					// Get indices of non-whitespace characters only
					const nonWhitespaceIndices = [];
					textArray.forEach((char, index) => {
						if (char.trim() !== '') { // Skip spaces, tabs, newlines
							nonWhitespaceIndices.push(index);
						}
					});
					
					// Randomize percentage between 1% and 4%
					const randomPercentage = 0.01 + (Math.random() * 0.03);
					const numToGlitch = Math.floor(nonWhitespaceIndices.length * randomPercentage);
					const indicesToGlitch = new Set();
					
					// Pick random non-whitespace indices to glitch
					while (indicesToGlitch.size < numToGlitch && nonWhitespaceIndices.length > 0) {
						const randomIndex = nonWhitespaceIndices[Math.floor(Math.random() * nonWhitespaceIndices.length)];
						indicesToGlitch.add(randomIndex);
					}
					
					// Replace characters at those indices (preserving whitespace)
					indicesToGlitch.forEach(index => {
						textArray[index] = glitchChars[Math.floor(Math.random() * glitchChars.length)];
					});
					
					element.textContent = textArray.join('');
					
					// Schedule next glitch with random timing (less frequent)
					const nextDelay = 800 + Math.random() * 600; // Random between 800-1400ms
					const timeout = setTimeout(scheduleNextGlitch, nextDelay);
					glitchIntervals.set(commentId, timeout);
				}
				
				scheduleNextGlitch();
			}, 300); // Wait for fade back in
		}, 300); // Wait for fade out (matches CSS transition)
	}
	
	function stopTextGlitch(commentId: string) {
		const timeout = glitchIntervals.get(commentId);
		if (timeout) {
			clearTimeout(timeout);
			glitchIntervals.delete(commentId);
		}
		
		// Restore original text and switch back to proportional font
		const originalText = originalTexts.get(commentId);
		if (originalText) {
			const element = document.querySelector(`[data-comment-id="${commentId}"] .glitch-text`);
			if (element) {
				element.textContent = originalText;
				element.classList.remove('glitching');
				element.classList.remove('glitch');
			}
			originalTexts.delete(commentId);
		}
	}

	async function makeGuess(commentId: string, guess: 'reddit' | 'replicant', actualIsAi: boolean) {
		const correct = (guess === 'replicant' && actualIsAi) || (guess === 'reddit' && !actualIsAi);

		guessedComments.set(commentId, {
			guessed: true,
			correct: correct,
			userGuess: guess
		});

		// Mark that a guess was just made
		justMadeGuess = true;

		// Trigger reactivity
		guessedComments = guessedComments;

		// Start text glitching for AI comments IMMEDIATELY
		if (actualIsAi) {
			// Get the comment text
			const comment = getAllCommentsFlat(redditData?.comments || []).find(c => c.id === commentId);
			if (comment) {
				// Start font transition immediately with the reveal
				startTextGlitch(commentId, comment.content);
			}
		}

		// Save guess to backend in background (don't await - fire and forget)
		if (browser && currentPostId && anonymousUserId) {
			fetch(`${databaseManager.getApiUrl()}/api/users/guess`, {
				method: 'POST',
				headers: databaseManager.getHeaders(),
				body: JSON.stringify({
					anonymous_id: anonymousUserId,
					post_id: currentPostId,
					comment_id: commentId,
					guess: guess,
					is_correct: correct
				})
			}).catch(err => {
				console.error('Failed to save guess:', err);
			});
		}
	}

	// Constants for post truncation
	const POST_TRUNCATE_LENGTH = 750; // characters

	function shouldTruncatePost(content: string): boolean {
		return content && content.length > POST_TRUNCATE_LENGTH;
	}

	function getTruncatedPost(content: string): string {
		if (!shouldTruncatePost(content)) return content;

		// Find a good break point near the character limit (end of sentence or paragraph)
		let truncated = content.substring(0, POST_TRUNCATE_LENGTH);

		// Try to break at end of sentence
		const lastPeriod = truncated.lastIndexOf('.');
		const lastQuestion = truncated.lastIndexOf('?');
		const lastExclamation = truncated.lastIndexOf('!');

		const lastSentenceEnd = Math.max(lastPeriod, lastQuestion, lastExclamation);

		if (lastSentenceEnd > POST_TRUNCATE_LENGTH * 0.7) {
			truncated = content.substring(0, lastSentenceEnd + 1);
		}

		return truncated;
	}

	function flagAsObvious(commentId: string) {
		feedbackCommentId = commentId;

		// Find the comment content
		const comment = getAllCommentsFlat(redditData?.comments || []).find(c => c.id === commentId);
		feedbackCommentContent = comment ? comment.content : '';

		showFeedbackDialog = true;
		setTimeout(() => feedbackDialogVisible = true, 10);
	}

	async function submitFeedback() {
		if (!browser || !currentPostId || !anonymousUserId || !feedbackCommentId) return;

		feedbackSubmitting = true;

		try {
			const response = await fetch(`${databaseManager.getApiUrl()}/api/users/flag-obvious`, {
				method: 'POST',
				headers: databaseManager.getHeaders(),
				body: JSON.stringify({
					anonymous_id: anonymousUserId,
					post_id: currentPostId,
					comment_id: feedbackCommentId
				})
			});

			if (!response.ok) {
				throw new Error('Failed to flag comment');
			}

			// Mark this comment as flagged
			flaggedComments.add(feedbackCommentId);
			flaggedComments = flaggedComments; // Trigger reactivity

			// Close dialog
			closeFeedbackDialog();
		} catch (err) {
			console.error('Failed to flag comment as obvious:', err);
			alert('Failed to submit feedback. Please try again.');
		} finally {
			feedbackSubmitting = false;
		}
	}

	function closeFeedbackDialog() {
		feedbackDialogVisible = false;
		setTimeout(() => {
			showFeedbackDialog = false;
			feedbackCommentId = '';
			feedbackCommentContent = '';
			feedbackSubmitting = false;
		}, 300);
	}

	function showPrompt(comment: Comment) {
		promptDialogComment = comment;
		showPromptDialog = true;
	}

	function closePromptDialog() {
		showPromptDialog = false;
		promptDialogComment = null;
	}

	function createSimplifiedComment(comment: Comment): any {
		return {
			content: comment.content,
			is_ai: comment.is_ai,
			archetype_used: comment.archetype_used,
			replies: comment.replies.map(reply => createSimplifiedComment(reply))
		};
	}

	async function copyJsonToClipboard() {
		if (!redditData) return;

		const simplifiedData = {
			post: {
				title: redditData.post.title,
				content: redditData.post.content,
				subreddit: redditData.post.subreddit
			},
			comments: redditData.comments.map(comment => createSimplifiedComment(comment)),
			tyrell_agenda: tyrellAgenda
		};

		try {
			await navigator.clipboard.writeText(JSON.stringify(simplifiedData, null, 2));
			jsonCopied = true;
			setTimeout(() => {
				jsonCopied = false;
			}, 2000);
		} catch (err) {
			console.error('Failed to copy to clipboard:', err);
		}
	}

	// Calculate total comment count including nested replies
	$: totalCommentCount = redditData ? redditData.comments.reduce((total, comment) => {
		return total + getAllComments(comment).length;
	}, 0) : 0;
	
	// Cleanup timeouts on destroy
	onDestroy(() => {
		glitchIntervals.forEach(timeout => clearTimeout(timeout));
		glitchIntervals.clear();
		originalTexts.clear();
	});
</script>

<div class="min-h-screen text-gray-100 relative z-10">
	{#if loading}
		<div class="flex items-center justify-center min-h-screen">
			<div class="animate-pulse text-gray-300">Loading post...</div>
		</div>
	{:else if error}
		<div class="flex items-center justify-center min-h-screen">
			<div class="text-center">
				<div class="text-amber-400 mb-4">{error}</div>
				<a href="/subreddit" class="px-4 py-2 text-white rounded transition-all duration-200 hover:scale-105" style="background: linear-gradient(135deg, #1e3a8a, #3b82f6); border: 1px solid rgba(0, 212, 255, 0.3);">
					Choose Community
				</a>
			</div>
		</div>
	{:else if redditData}
		<!-- Fixed Toolbar -->
		<div class="fixed top-0 left-0 right-0 z-50 border-b border-gray-700" style="background: rgba(17, 17, 20, 0.95); backdrop-filter: blur(10px);">
			<div class="max-w-4xl mx-auto px-4 md:px-0 py-3">
				<div class="flex items-center justify-between">
					<!-- Back Button & Title -->
					<div class="flex items-center gap-4">
						<a href={currentSubreddit ? `/subreddit/${currentSubreddit}` : '/subreddit'} class="transition-colors flex items-center gap-1" style="color: #00d4ff;" on:mouseenter={(e) => e.target.style.color='#33e0ff'} on:mouseleave={(e) => e.target.style.color='#00d4ff'}>
							← Back
						</a>
						<h1 class="text-lg font-bold hidden sm:block" style="color: #f3f4f6; text-shadow: 0 0 8px rgba(0, 212, 255, 0.1);">
							Reddit or <span class="glitch" data-text="Replicant">Replicant</span>?
						</h1>
					</div>
					
					<!-- Stats -->
					<div class="flex items-center gap-6 text-sm">
						<div class="flex items-center gap-2">
							<span style="color: #4ade80;">✓</span>
							<span class="text-gray-300">{correctGuesses}</span>
						</div>
						<div class="flex items-center gap-2">
							<span style="color: #f87171;">✗</span>
							<span class="text-gray-300">{incorrectGuesses}</span>
						</div>
						{#if remainingGuesses > 0}
							<div class="flex items-center gap-2">
								<span style="color: #00d4ff;">Remaining:</span>
								<span class="text-gray-200 font-medium">{remainingGuesses}</span>
							</div>
						{:else if totalGuessed > 0}
							<button 
								on:click={showResults}
								class="px-2 py-1 text-xs rounded transition-all duration-200 hover:scale-105 cursor-pointer"
								style="background: rgba(0, 212, 255, 0.2); color: #00d4ff; border: 1px solid rgba(0, 212, 255, 0.3);"
								title="View your final results"
							>
								Review Results
							</button>
						{/if}
						{#if totalGuessed > 0}
							<button 
								on:click={resetProgress}
								class="px-2 py-1 text-xs rounded transition-all duration-200 hover:scale-105 cursor-pointer"
								style="background: rgba(248, 113, 113, 0.2); color: #f87171; border: 1px solid rgba(248, 113, 113, 0.3);"
								title="Reset all progress on this post"
							>
								Reset
							</button>
						{/if}
					</div>
				</div>
			</div>
		</div>

		<!-- Content with top padding to account for fixed toolbar -->
		<div class="pt-16">
		<div class="max-w-4xl mx-auto" style="background: rgba(17, 17, 20, 0.85); backdrop-filter: blur(10px); border: 1px solid rgba(55, 65, 81, 0.3); box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);">
			<!-- Post -->
			{#if redditData.post}
				<div class="border-b border-gray-700 p-6">
					<div class="mb-4">
						<!-- Desktop Layout -->
						<div class="hidden sm:flex justify-between items-center">
							<div>
								<span class="text-sm" style="color: #00d4ff; text-shadow: 0 0 8px rgba(0, 212, 255, 0.3);">r/{redditData.post.subreddit}</span>
								<span class="text-sm text-gray-400 ml-2">• Posted by u/{redditData.post.author}</span>
							</div>
							{#if isLocalEnvironment}
								<button
									on:click={copyJsonToClipboard}
									class="text-xs px-2 py-1 rounded transition-all duration-200 hover:scale-105 cursor-pointer"
									style="background: rgba(75, 85, 99, 0.8); border: 1px solid #6b7280; color: #d1d5db;"
								>
									{#if jsonCopied}
										✓ Copied
									{:else}
										Copy JSON
									{/if}
								</button>
							{/if}
						</div>
						<!-- Mobile Layout -->
						<div class="sm:hidden">
							<div class="flex justify-between items-start">
								<div>
									<div class="text-sm" style="color: #00d4ff; text-shadow: 0 0 8px rgba(0, 212, 255, 0.3);">r/{redditData.post.subreddit}</div>
									<div class="text-sm text-gray-400">Posted by u/{redditData.post.author}</div>
								</div>
								{#if isLocalEnvironment}
									<button
										on:click={copyJsonToClipboard}
										class="text-xs px-2 py-1 rounded transition-all duration-200 hover:scale-105 ml-2 cursor-pointer"
										style="background: rgba(75, 85, 99, 0.8); border: 1px solid #6b7280; color: #d1d5db;"
									>
										{#if jsonCopied}
											✓ Copied
										{:else}
											Copy JSON
										{/if}
									</button>
								{/if}
							</div>
						</div>
					</div>
					<h1 class="text-2xl font-bold mb-4" style="color: #f3f4f6; text-shadow: 0 0 12px rgba(0, 212, 255, 0.1);">{redditData.post.title}</h1>
					{#if redditData.post.content}
						<div class="text-gray-200 mb-4">
							<div class="whitespace-pre-wrap content-text">
								{#if shouldTruncatePost(redditData.post.content) && !postExpanded}
									{@html getTruncatedPost(redditData.post.content)}
								{:else}
									{@html redditData.post.content}
								{/if}
							</div>
							{#if shouldTruncatePost(redditData.post.content)}
								<div class="mt-2">
									{#if !postExpanded}
										<button
											class="text-sm underline opacity-70 hover:opacity-100 transition-opacity cursor-pointer"
											style="color: #00d4ff;"
											on:click={() => postExpanded = true}
										>
											Read more
										</button>
									{:else}
										<button
											class="text-sm underline opacity-70 hover:opacity-100 transition-opacity cursor-pointer"
											style="color: #00d4ff;"
											on:click={() => postExpanded = false}
										>
											Show less
										</button>
									{/if}
								</div>
							{/if}
						</div>
					{/if}
					<div class="text-sm text-gray-400">
						{redditData.post.score} points • {totalCommentCount} comments
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
							<div class="comment mb-3 p-3 rounded-lg bg-gray-750" 
								 style="margin-left: {flatComment.depth * 32}px"
								 data-comment-id={flatComment.id}>
								<div class="border-l-2 pl-3" style="border-color: rgba(75, 85, 99, 0.4);">
									<div class="text-sm text-gray-400 mb-2">
										{#if guessState?.guessed && flatComment.is_ai}
											<span class="font-medium glitch" data-text="REPLICANT" in:fade={{ duration: 300 }}>REPLICANT</span>
										{:else}
											<span class="font-medium" style="color: #00d4ff; text-shadow: 0 0 8px rgba(0, 212, 255, 0.2);">u/{flatComment.author}</span>
										{/if}
										<span class="ml-2">{flatComment.score} points</span>
									</div>
									
									{#if flatComment.content_html}
										<div class="mb-3 prose prose-invert prose-sm max-w-none text-gray-200 content-text glitch-text" 
											 data-text={flatComment.content}>
											{@html flatComment.content_html}
										</div>
									{:else}
										<div class="mb-3 whitespace-pre-wrap text-gray-200 content-text glitch-text" 
											 data-text={flatComment.content}>
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
													style="background: linear-gradient(135deg, #164e63, #0891b2); border: 1px solid rgba(0, 212, 255, 0.3);"
													on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px rgba(0, 212, 255, 0.4)'}
													on:mouseleave={(e) => e.target.style.boxShadow = ''}
													on:click={() => makeGuess(flatComment.id, 'reddit', flatComment.is_ai)}
												>
													Reddit
												</button>
												<button 
													class="px-2 py-1 text-white rounded text-xs transition-all duration-200 hover:scale-105 hover:shadow-lg cursor-pointer"
													style="background: linear-gradient(135deg, var(--replicant-primary), var(--replicant-secondary)); border: 1px solid var(--replicant-border);"
													on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px var(--replicant-glow)'}
													on:mouseleave={(e) => e.target.style.boxShadow = ''}
													on:click={() => makeGuess(flatComment.id, 'replicant', flatComment.is_ai)}
												>
													Replicant
												</button>
											</div>
										{:else}
											<!-- Desktop Layout -->
											<div class="hidden sm:flex gap-3 items-center">
												<span class="text-xs text-gray-400">Origin:</span>
												<button
													class="px-2 py-1 rounded text-xs cursor-not-allowed"
													class:bg-cyan-700={guessState.userGuess === 'reddit'}
													class:bg-gray-600={guessState.userGuess !== 'reddit'}
													class:text-white={guessState.userGuess === 'reddit'}
													class:text-gray-400={guessState.userGuess !== 'reddit'}
													disabled
												>
													Reddit {guessState.userGuess === 'reddit' ? '✓' : ''}
												</button>
												<button
													class="px-2 py-1 rounded text-xs cursor-not-allowed"
													class:bg-red-700={guessState.userGuess === 'replicant'}
													class:bg-gray-600={guessState.userGuess !== 'replicant'}
													class:text-white={guessState.userGuess === 'replicant'}
													class:text-gray-400={guessState.userGuess !== 'replicant'}
													disabled
												>
													Replicant {guessState.userGuess === 'replicant' ? '✓' : ''}
												</button>
												<div class="text-xs ml-2" in:fade={{ duration: 300, delay: 100 }}>
													{#if guessState.correct}
														<span style="color: #4ade80;">✓ {flatComment.is_ai ? 'Replicant identified' : 'Reddit origin confirmed'}.</span>
														{#if flatComment.is_ai}
															<button
																class="ml-2 text-xs transition-opacity"
																class:underline={!flaggedComments.has(flatComment.id)}
																class:opacity-70={!flaggedComments.has(flatComment.id)}
																class:hover:opacity-100={!flaggedComments.has(flatComment.id)}
																class:cursor-pointer={!flaggedComments.has(flatComment.id)}
																class:opacity-60={flaggedComments.has(flatComment.id)}
																style="color: #f59e0b;"
																on:click={() => flagAsObvious(flatComment.id)}
																title="Flag this AI comment as too obvious to help improve our generation"
																disabled={flaggedComments.has(flatComment.id)}
															>
																{flaggedComments.has(flatComment.id) ? 'Feedback submitted' : 'Too obvious?'}
															</button>
														{/if}
													{:else}
														<span style="color: #f87171;">✗ Detection failed. This {flatComment.is_ai ? 'was a replicant' : 'is from Reddit'}.</span>
													{/if}
													{#if flatComment.is_ai && isLocalEnvironment && (flatComment.generation_prompt || flatComment.archetype_used)}
														<button
															class="ml-2 text-xs underline opacity-70 hover:opacity-100 transition-opacity cursor-pointer"
															style="color: #a78bfa;"
															on:click={() => showPrompt(flatComment)}
															title="View the archetype and prompt used to generate this comment"
														>
															Show Prompt
														</button>
													{/if}
												</div>
											</div>

											<!-- Mobile Layout -->
											<div class="sm:hidden">
												<div class="flex gap-3 items-center mb-2">
													<span class="text-xs text-gray-400">Origin:</span>
													<button
														class="px-2 py-1 rounded text-xs cursor-not-allowed"
														class:bg-cyan-700={guessState.userGuess === 'reddit'}
														class:bg-gray-600={guessState.userGuess !== 'reddit'}
														class:text-white={guessState.userGuess === 'reddit'}
														class:text-gray-400={guessState.userGuess !== 'reddit'}
														disabled
													>
														Reddit {guessState.userGuess === 'reddit' ? '✓' : ''}
													</button>
													<button
														class="px-2 py-1 rounded text-xs cursor-not-allowed"
														class:bg-red-700={guessState.userGuess === 'replicant'}
														class:bg-gray-600={guessState.userGuess !== 'replicant'}
														class:text-white={guessState.userGuess === 'replicant'}
														class:text-gray-400={guessState.userGuess !== 'replicant'}
														disabled
													>
														Replicant {guessState.userGuess === 'replicant' ? '✓' : ''}
													</button>
												</div>
												<div class="text-xs" in:fade={{ duration: 300, delay: 100 }}>
													{#if guessState.correct}
														<span style="color: #4ade80;">✓ {flatComment.is_ai ? 'Replicant identified' : 'Reddit origin confirmed'}.</span>
														{#if flatComment.is_ai}
															<button
																class="ml-2 text-xs transition-opacity"
																class:underline={!flaggedComments.has(flatComment.id)}
																class:opacity-70={!flaggedComments.has(flatComment.id)}
																class:hover:opacity-100={!flaggedComments.has(flatComment.id)}
																class:cursor-pointer={!flaggedComments.has(flatComment.id)}
																class:opacity-60={flaggedComments.has(flatComment.id)}
																style="color: #f59e0b;"
																on:click={() => flagAsObvious(flatComment.id)}
																title="Flag this AI comment as too obvious to help improve our generation"
																disabled={flaggedComments.has(flatComment.id)}
															>
																{flaggedComments.has(flatComment.id) ? 'Feedback submitted' : 'Too obvious?'}
															</button>
														{/if}
													{:else}
														<span style="color: #f87171;">✗ Detection failed. This {flatComment.is_ai ? 'was a replicant' : 'is from Reddit'}.</span>
													{/if}
													{#if flatComment.is_ai && isLocalEnvironment && (flatComment.generation_prompt || flatComment.archetype_used)}
														<button
															class="ml-2 text-xs underline opacity-70 hover:opacity-100 transition-opacity cursor-pointer"
															style="color: #a78bfa;"
															on:click={() => showPrompt(flatComment)}
															title="View the archetype and prompt used to generate this comment"
														>
															Show Prompt
														</button>
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
		</div>
	{/if}
</div>

<!-- Results Dialog -->
{#if showResultsDialog}
	<div 
		class="fixed inset-0 flex items-center justify-center z-50 transition-opacity duration-300"
		class:opacity-0={!resultsDialogVisible}
		class:opacity-100={resultsDialogVisible}
		style="background: rgba(0, 0, 0, 0.7); backdrop-filter: blur(4px);"
		on:click={closeResultsDialog}
	>
		<div 
			class="border border-gray-700 rounded-lg p-8 m-4 max-w-2xl w-full transform transition-all duration-300"
			class:scale-95={!resultsDialogVisible}
			class:opacity-0={!resultsDialogVisible}
			class:scale-100={resultsDialogVisible}
			class:opacity-100={resultsDialogVisible}
			style="background: rgba(17, 17, 20, 0.95); backdrop-filter: blur(10px);"
			on:click|stopPropagation
		>
			<div class="text-center">
				<h2 class="text-2xl font-bold mb-6" style="color: #f3f4f6; text-shadow: 0 0 12px rgba(0, 212, 255, 0.1);">
					Detection <span class="glitch" data-text="Complete">Complete</span>
				</h2>
				
				<!-- Results Stats -->
				<div class="grid grid-cols-3 gap-6 mb-8">
					<div class="text-center">
						<div class="text-3xl font-bold mb-2" style="color: #4ade80;">{correctGuesses}</div>
						<div class="text-sm text-gray-400">Correct</div>
					</div>
					<div class="text-center">
						<div class="text-3xl font-bold mb-2" style="color: #f87171;">{incorrectGuesses}</div>
						<div class="text-sm text-gray-400">Incorrect</div>
					</div>
					<div class="text-center">
						<div class="text-3xl font-bold mb-2" style="color: #00d4ff;">{Math.round(accuracy * 100)}%</div>
						<div class="text-sm text-gray-400">Accuracy</div>
					</div>
				</div>
				
				<!-- Assessment Message -->
				<div class="mb-8 p-4 rounded-lg border border-gray-600" style="background: rgba(31, 31, 35, 0.6);">
					<p class="text-gray-200 leading-relaxed">
						{getResultMessage(accuracy)}
					</p>
				</div>

				<!-- Tyrell's Agenda Reveal -->
				{#if tyrellAgenda}
					<div class="mb-8 p-4 rounded-lg border border-red-600" style="background: rgba(40, 20, 20, 0.6);">
						<h3 class="text-lg font-bold mb-3" style="color: #ff6b6b; text-shadow: 0 0 8px rgba(255, 107, 107, 0.3);">
							Tyrell's Directive
						</h3>
						<p class="text-gray-200 leading-relaxed italic">
							"{tyrellAgenda}"
						</p>
					</div>
				{/if}

				<!-- Action Buttons -->
				<div class="flex justify-end gap-3">
					<button 
						on:click={closeResultsDialog}
						class="px-4 py-2 text-white rounded transition-all duration-200 hover:scale-105 cursor-pointer"
						style="background: #4b5563; border: 1px solid #6b7280;"
					>
						Close
					</button>
					<a 
						href="/subreddit"
						class="px-4 py-2 text-white rounded transition-all duration-200 hover:scale-105 cursor-pointer inline-block text-center"
						style="background: linear-gradient(135deg, var(--replicant-dark), var(--replicant-light)); border: 1px solid var(--replicant-border);"
						on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px var(--replicant-glow)'}
						on:mouseleave={(e) => e.target.style.boxShadow = ''}
					>
						Next Test
					</a>
				</div>
			</div>
		</div>
	</div>
{/if}

<!-- Feedback Dialog -->
{#if showFeedbackDialog}
	<div
		class="fixed inset-0 flex items-center justify-center z-50 transition-opacity duration-300"
		class:opacity-0={!feedbackDialogVisible}
		class:opacity-100={feedbackDialogVisible}
		style="background: rgba(0, 0, 0, 0.7); backdrop-filter: blur(4px);"
		on:click={closeFeedbackDialog}
	>
		<div
			class="border border-gray-700 rounded-lg p-8 m-4 max-w-md sm:max-w-2xl w-full transform transition-all duration-300"
			class:scale-95={!feedbackDialogVisible}
			class:opacity-0={!feedbackDialogVisible}
			class:scale-100={feedbackDialogVisible}
			class:opacity-100={feedbackDialogVisible}
			style="background: rgba(17, 17, 20, 0.95); backdrop-filter: blur(10px);"
			on:click|stopPropagation
		>
			<div class="text-center">
				<h2 class="text-xl font-bold mb-4" style="color: #f3f4f6; text-shadow: 0 0 8px rgba(0, 212, 255, 0.1);">
					Help Improve Our System
				</h2>

				<!-- Comment Preview -->
				{#if feedbackCommentContent}
					<div class="mb-4 p-3 rounded border border-gray-600 text-left" style="background: rgba(31, 31, 35, 0.6);">
						<div class="text-xs text-gray-400 mb-2">Comment:</div>
						<div class="text-gray-200 text-sm max-h-32 overflow-y-auto">
							{feedbackCommentContent}
						</div>
					</div>
				{/if}

				<p class="text-gray-300 mb-6 leading-relaxed text-left">
					Was it too obvious that this comment was generated by AI? Your feedback helps us create more realistic content.
				</p>

				<!-- Action Buttons -->
				<div class="flex justify-end gap-3">
					<button
						on:click={closeFeedbackDialog}
						class="px-4 py-2 text-white rounded transition-all duration-200 hover:scale-105 cursor-pointer"
						style="background: #4b5563; border: 1px solid #6b7280;"
						disabled={feedbackSubmitting}
					>
						Cancel
					</button>
					<button
						on:click={submitFeedback}
						class="px-4 py-2 text-white rounded transition-all duration-200 hover:scale-105 cursor-pointer flex items-center gap-2"
						style="background: linear-gradient(135deg, #dc2626, #ef4444); border: 1px solid #f87171;"
						on:mouseenter={(e) => !feedbackSubmitting && (e.target.style.boxShadow = '0 0 15px rgba(248, 113, 113, 0.4)')}
						on:mouseleave={(e) => e.target.style.boxShadow = ''}
						disabled={feedbackSubmitting}
					>
						{#if feedbackSubmitting}
							<div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
							Submitting...
						{:else}
							Too Obvious
						{/if}
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}

<!-- Show Prompt Dialog -->
{#if showPromptDialog && promptDialogComment}
	<div
		class="fixed inset-0 flex items-center justify-center z-50 transition-opacity duration-300"
		style="background: rgba(0, 0, 0, 0.7); backdrop-filter: blur(4px);"
		on:click={closePromptDialog}
	>
		<div
			class="border border-gray-700 rounded-lg p-8 m-4 max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col"
			style="background: rgba(17, 17, 20, 0.95); backdrop-filter: blur(10px);"
			on:click|stopPropagation
		>
			<div class="flex justify-between items-center mb-6">
				<h2 class="text-xl font-bold" style="color: #f3f4f6; text-shadow: 0 0 8px rgba(0, 212, 255, 0.1);">
					AI Generation Details
				</h2>
				<button
					on:click={closePromptDialog}
					class="text-gray-400 hover:text-white transition-colors cursor-pointer text-xl"
					title="Close"
				>
					×
				</button>
			</div>

			<div class="flex-1 flex flex-col lg:flex-row gap-6 overflow-hidden">
				<!-- Left side: Archetype + Generated Comment -->
				<div class="flex flex-col flex-1 min-w-0">
					{#if promptDialogComment.archetype_used}
						<div class="mb-4">
							<h3 class="text-sm font-semibold mb-2" style="color: #a78bfa;">Archetype:</h3>
							<div class="p-3 rounded border border-gray-600 text-sm" style="background: rgba(31, 31, 35, 0.6); color: #e5e7eb;">
								{promptDialogComment.archetype_used}
							</div>
						</div>
					{/if}

					<h3 class="text-sm font-semibold mb-3" style="color: #a78bfa;">Generated Comment:</h3>
					<div class="flex-1 p-4 rounded border border-gray-600 text-sm overflow-y-auto min-h-0" style="background: rgba(31, 31, 35, 0.6);">
						<div class="text-xs text-gray-400 mb-3">
							<span class="font-medium" style="color: #00d4ff;">u/{promptDialogComment.author}</span>
							<span class="ml-2">{promptDialogComment.score} points</span>
						</div>
						{#if promptDialogComment.content_html}
							<div class="prose prose-invert prose-sm max-w-none text-gray-200 leading-relaxed">
								{@html promptDialogComment.content_html}
							</div>
						{:else}
							<div class="whitespace-pre-wrap text-gray-200 leading-relaxed">
								{promptDialogComment.content}
							</div>
						{/if}
					</div>
				</div>

				<!-- Right side: Generation Prompt -->
				<div class="flex flex-col flex-1 min-w-0">
					{#if promptDialogComment.generation_prompt}
						<h3 class="text-sm font-semibold mb-3" style="color: #a78bfa;">Generation Prompt:</h3>
						<div class="flex-1 p-3 rounded border border-gray-600 text-sm whitespace-pre-wrap overflow-y-auto min-h-0" style="background: rgba(31, 31, 35, 0.6); color: #e5e7eb;">
							{promptDialogComment.generation_prompt}
						</div>
					{:else}
						<div class="flex-1 flex items-center justify-center text-center text-gray-400">
							No generation prompt available for this comment.
						</div>
					{/if}
				</div>
			</div>

			<div class="flex justify-end pt-3 border-t border-gray-600">
				<button
					on:click={closePromptDialog}
					class="px-3 py-1.5 text-white rounded transition-all duration-200 hover:scale-105 cursor-pointer text-sm"
					style="background: #4b5563; border: 1px solid #6b7280;"
				>
					Close
				</button>
			</div>
		</div>
	</div>
{/if}
