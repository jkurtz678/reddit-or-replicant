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
			const response = await fetch('/api/test-reddit');
			if (!response.ok) throw new Error('Failed to fetch');
			redditData = await response.json();
		} catch (err) {
			error = 'Failed to load Reddit data';
			console.error(err);
		} finally {
			loading = false;
		}
	});

	function getAllComments(comment: Comment, allComments: Comment[] = []): Comment[] {
		allComments.push(comment);
		if (comment.replies && comment.replies.length > 0) {
			comment.replies.forEach((reply: Comment) => {
				getAllComments(reply, allComments);
			});
		}
		return allComments;
	}
</script>

<div class="min-h-screen bg-gray-900 text-gray-100">
	{#if loading}
		<div class="p-8">
			<div class="animate-pulse text-gray-300">Loading Reddit data...</div>
		</div>
	{:else if error}
		<div class="p-8 text-red-400">
			{error}
		</div>
	{:else if redditData}
		<div class="max-w-4xl mx-auto bg-gray-800">
			<!-- Post -->
			{#if redditData.post}
				<div class="border-b border-gray-700 p-6">
					<div class="mb-4">
						<span class="text-sm text-orange-400">r/{redditData.post.subreddit}</span>
						<span class="text-sm text-gray-400 ml-2">• Posted by u/{redditData.post.author}</span>
					</div>
					<h1 class="text-2xl font-bold mb-4 text-white">{redditData.post.title}</h1>
					{#if redditData.post.content}
						<div class="text-gray-200 mb-4 whitespace-pre-wrap">{redditData.post.content}</div>
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
							<div class="comment mb-4" style="margin-left: {flatComment.depth * 20}px">
								<div class="border-l-2 border-gray-600 pl-4">
									<div class="text-sm text-gray-400 mb-2">
										<span class="font-medium text-blue-400">u/{flatComment.author}</span>
										<span class="ml-2">{flatComment.score} points</span>
										{#if flatComment.is_ai}
											<span class="ml-2 text-xs bg-purple-600 text-purple-100 px-2 py-1 rounded">AI</span>
										{/if}
									</div>
									{#if flatComment.content_html}
										<div class="text-gray-200 mb-3 prose prose-invert prose-sm max-w-none">{@html flatComment.content_html}</div>
									{:else}
										<div class="text-gray-200 mb-3 whitespace-pre-wrap">{flatComment.content}</div>
									{/if}
								</div>
							</div>
						{/each}
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>
