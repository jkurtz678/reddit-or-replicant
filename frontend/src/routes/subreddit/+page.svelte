<script lang="ts">
	import { goto } from '$app/navigation';

	// Hardcoded subreddits with descriptions
	const subreddits = [
		{
			name: 'news',
			display: 'r/news',
			description: 'Breaking news and current events from around the world.'
		},
		{
			name: 'unpopularopinion',
			display: 'r/unpopularopinion',
			description: 'Controversial takes and unconventional perspectives.'
		},
		{
			name: 'changemyview',
			display: 'r/changemyview',
			description: 'Discussions aimed at changing people\'s minds.'
		}
	];

	function selectSubreddit(subredditName: string) {
		goto(`/subreddit/${subredditName}`);
	}
</script>

<svelte:head>
	<title>Choose a Community - Reddit or Replicant</title>
</svelte:head>

<div class="min-h-screen text-gray-100" style="background: linear-gradient(180deg, #0a0a0b 0%, #111013 100%)">
	<!-- Fixed Toolbar -->
	<div class="fixed top-0 left-0 right-0 z-50 border-b border-gray-700" style="background: rgba(17, 17, 20, 0.95); backdrop-filter: blur(10px);">
		<div class="max-w-6xl mx-auto px-4 md:px-0 py-3">
			<div class="flex items-center justify-between">
				<a href="/" class="text-lg font-bold cursor-pointer hover:text-blue-300 transition-colors" style="color: #f3f4f6; text-shadow: 0 0 8px rgba(0, 212, 255, 0.1);">
					Reddit or <span class="glitch" data-text="Replicant">Replicant</span>?
				</a>
				<div class="flex items-center gap-4">
					<a href="/about" class="transition-colors text-sm" style="color: #00d4ff;" >
						About
					</a>
				</div>
			</div>
		</div>
	</div>

	<!-- Content with top padding to account for fixed toolbar -->
	<div class="pt-16">
		<div class="container mx-auto p-8 md:px-0">
			<div class="max-w-6xl mx-auto">
				<!-- Header -->
				<div class="text-center mb-12">
					<h1 class="text-3xl font-bold mb-4" style="color: #f3f4f6; text-shadow: 0 0 12px rgba(0, 212, 255, 0.1);">
						Select a Subreddit
					</h1>
					<p class="text-gray-400 text-lg max-w-2xl mx-auto">
						Select a community to test your ability to detect AI-generated content.
					</p>
				</div>

				<!-- Subreddit Cards -->
				<div class="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
					{#each subreddits as subreddit}
						<div 
							class="border border-gray-700 rounded-lg p-8 cursor-pointer transition-all duration-200 hover:border-blue-400 hover:scale-105"
							style="background: rgba(17, 17, 20, 0.85); backdrop-filter: blur(10px);"
							on:click={() => selectSubreddit(subreddit.name)}
							on:keydown={(e) => e.key === 'Enter' && selectSubreddit(subreddit.name)}
							role="button"
							tabindex="0"
						>
							<div class="text-center">
								<h3 class="text-xl font-semibold mb-4" style="color: #00d4ff; text-shadow: 0 0 8px rgba(0, 212, 255, 0.2);">
									{subreddit.display}
								</h3>
								<p class="text-gray-300 leading-relaxed content-text">
									{subreddit.description}
								</p>
								<div class="mt-6">
									<button 
										class="px-6 py-2 text-white rounded transition-all duration-200 hover:scale-105 cursor-pointer"
										style="background: linear-gradient(135deg, var(--replicant-primary), var(--replicant-secondary)); border: 1px solid var(--replicant-border);"
										on:mouseenter={(e) => e.target.style.boxShadow = '0 0 15px var(--replicant-glow)'}
										on:mouseleave={(e) => e.target.style.boxShadow = ''}
									>
										Enter Community
									</button>
								</div>
							</div>
						</div>
					{/each}
				</div>
			</div>
		</div>
	</div>
</div>