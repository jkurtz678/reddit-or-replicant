<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount, onDestroy } from 'svelte';

	let canvas: HTMLCanvasElement;
	let animationId: number;

	function takeTest() {
		goto('/selection');
	}

	onMount(() => {
		if (!canvas) return;

		const gl = canvas.getContext('webgl');
		if (!gl) return;

		// Vertex shader
		const vertexShaderSource = `
			attribute vec2 a_position;
			void main() {
				gl_Position = vec4(a_position, 0.0, 1.0);
			}
		`;

		// Fragment shader (digital rain effect)
		const fragmentShaderSource = `
			#ifdef GL_ES
			precision mediump float;
			#endif
			uniform vec2 u_resolution;
			uniform vec2 u_mouse;
			uniform float u_time;
			
			float random (in float x) {
				return fract(sin(x)*1e4);
			}
			
			float random (in vec2 st) {
				return fract(sin(dot(st.xy, vec2(12.9898,78.233)))* 43758.5453123);
			}
			
			float pattern(vec2 st, vec2 v, float t) {
				vec2 p = floor(st+v);
				return step(t, random(100.+p*.000001)+random(p.x)*0.5 );
			}
			
			void main() {
				vec2 st = gl_FragCoord.xy/u_resolution.xy;
				st.x *= u_resolution.x/u_resolution.y;
				
				float m_offset = 0.0;
				vec2 grid = vec2(100.0,50.);
				st *= grid;
				
				vec2 ipos = floor(st);
				vec2 fpos = fract(st);
				vec2 vel = vec2(u_time*0.5*max(grid.x,grid.y));
				vel *= vec2(-1.,0.0) * random(1.0+ipos.y);
				
				vec2 offset = vec2(0.1,0.);
				vec3 color = vec3(0.);
				color.r = pattern(st+offset,vel,0.5+m_offset);
				color.g = pattern(st,vel,0.5+m_offset);
				color.b = pattern(st-offset,vel,0.5+m_offset);
				
				// Cyberpunk color palette
				// vec3 cyan = vec3(0.0, 1.0, 1.0);
				// vec3 magenta = vec3(1.0, 0.0, 1.0);
				// vec3 neonGreen = vec3(0.0, 1.0, 0.3);
				
				// vec3 cyberpunkColor = color.r * cyan + color.g * neonGreen + color.b * magenta;
				// color = mix(color, cyberpunkColor, 0.9);
				
				// Neon pulse
				color *= (1.2 + sin(u_time * 1.5) * 0.2);
				
				// Scanlines
				float scanline = sin((gl_FragCoord.y / u_resolution.y) * 800.0) * 0.04;
				color += scanline;
				
				// Random glitch
				float glitch = step(0.99, random(floor(u_time * 15.0) + ipos.y));
				color += glitch * vec3(0.5, 0.0, 0.8) * random(u_time + ipos.x);
				
				// CRT vignette
				vec2 crt = (gl_FragCoord.xy / u_resolution.xy) * 2.0 - 1.0;
				float vignette = 1.0 - dot(crt, crt) * 0.3;
				color *= vignette;
				
				// Margins
				color *= step(0.2,fpos.y);
				
				gl_FragColor = vec4((color * 1.0) * 0.1, 1.0);
			}
		`;

		function createShader(gl: WebGLRenderingContext, type: number, source: string) {
			const shader = gl.createShader(type);
			if (!shader) return null;
			
			gl.shaderSource(shader, source);
			gl.compileShader(shader);
			
			if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
				console.error('Shader compile error:', gl.getShaderInfoLog(shader));
				gl.deleteShader(shader);
				return null;
			}
			
			return shader;
		}

		function createProgram(gl: WebGLRenderingContext, vertexShader: WebGLShader, fragmentShader: WebGLShader) {
			const program = gl.createProgram();
			if (!program) return null;
			
			gl.attachShader(program, vertexShader);
			gl.attachShader(program, fragmentShader);
			gl.linkProgram(program);
			
			if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
				console.error('Program link error:', gl.getProgramInfoLog(program));
				gl.deleteProgram(program);
				return null;
			}
			
			return program;
		}

		// Create shaders
		const vertexShader = createShader(gl, gl.VERTEX_SHADER, vertexShaderSource);
		const fragmentShader = createShader(gl, gl.FRAGMENT_SHADER, fragmentShaderSource);
		
		if (!vertexShader || !fragmentShader) return;

		// Create program
		const program = createProgram(gl, vertexShader, fragmentShader);
		if (!program) return;

		// Set up geometry (full screen quad)
		const positionBuffer = gl.createBuffer();
		gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
		gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
			-1, -1,
			 1, -1,
			-1,  1,
			 1,  1
		]), gl.STATIC_DRAW);

		const positionLocation = gl.getAttribLocation(program, 'a_position');
		const resolutionLocation = gl.getUniformLocation(program, 'u_resolution');
		const timeLocation = gl.getUniformLocation(program, 'u_time');
		const mouseLocation = gl.getUniformLocation(program, 'u_mouse');

		let mouseX = 0;
		let mouseY = 0;

		function resizeCanvas() {
			canvas.width = window.innerWidth;
			canvas.height = window.innerHeight;
			gl.viewport(0, 0, canvas.width, canvas.height);
		}

		function render(time: number) {
			gl.useProgram(program);

			gl.uniform2f(resolutionLocation, canvas.width, canvas.height);
			gl.uniform1f(timeLocation, time * 0.001); // Convert to seconds
			gl.uniform2f(mouseLocation, mouseX, mouseY);

			gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
			gl.enableVertexAttribArray(positionLocation);
			gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);

			gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);

			animationId = requestAnimationFrame(render);
		}

		function handleMouseMove(event: MouseEvent) {
			mouseX = event.clientX;
			mouseY = canvas.height - event.clientY; // Flip Y coordinate
		}

		resizeCanvas();
		window.addEventListener('resize', resizeCanvas);
		//window.addEventListener('mousemove', handleMouseMove);
		render(0);

		return () => {
			window.removeEventListener('resize', resizeCanvas);
			//window.removeEventListener('mousemove', handleMouseMove);
		};
	});

	onDestroy(() => {
		if (animationId) {
			cancelAnimationFrame(animationId);
		}
	});
</script>

<!-- Shader background canvas -->
<canvas bind:this={canvas} class="fixed inset-0 w-full h-full" style="z-index: -1;"></canvas>


<div class="min-h-screen text-gray-100 flex items-center justify-center relative z-10">
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