<script lang="ts">
	import { goto } from '$app/navigation';

	function takeTest() {
		goto('/selection');
	}
</script>

<div class="min-h-screen text-gray-100 flex items-center justify-center" style="background: linear-gradient(180deg, #0a0a0b 0%, #111013 100%)">
	<div class="text-center max-w-3xl mx-auto px-8">
		<h1 class="text-5xl font-bold mb-8" style="color: #f3f4f6; text-shadow: 0 0 12px rgba(0, 212, 255, 0.1);">
			Reddit or <span class="glitch" data-text="Replicant">Replicant</span>?
		</h1>
		
		<div class="max-w-2xl mx-auto space-y-4 mb-12">
			<p class="text-gray-200 text-2xl leading-relaxed font-medium">
				Your social media feed is flooded with AI content designed to manipulate you.
			</p>
			<p class="text-gray-200 text-2xl leading-relaxed font-medium">
				Can you tell what's real?
			</p>
		</div>

		<button 
			on:click={takeTest}
			class="px-8 py-4 text-white text-xl rounded transition-all duration-200 cursor-pointer hover:scale-105 font-semibold"
			style="background: linear-gradient(135deg, #1e3a8a, #3b82f6); border: 1px solid rgba(0, 212, 255, 0.3); box-shadow: 0 4px 15px rgba(0, 212, 255, 0.2);"
			on:mouseenter={(e) => e.target.style.boxShadow = '0 6px 25px rgba(0, 212, 255, 0.4)'}
			on:mouseleave={(e) => e.target.style.boxShadow = '0 4px 15px rgba(0, 212, 255, 0.2)'}
		>
			Take the Test
		</button>
	</div>
</div>