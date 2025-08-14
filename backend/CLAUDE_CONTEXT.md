# Replicant Project - Complete Context

## Project Overview & Goals
Web application called "Replicant" that demonstrates how difficult it is to distinguish AI-generated content from human content on social media. Users are presented with Reddit comments and must guess whether they're real Reddit comments or AI-generated "Replicant" comments. The goal is to raise awareness about AI content manipulation.

**Core Concept**: Create a guessing game where users identify AI vs human Reddit comments to highlight the difficulty of detecting AI-generated social media content.

**Aesthetic**: Cyberpunk/Blade Runner theme with glitch effects, dark colors, and futuristic UI elements.

## Technical Architecture

### Backend (FastAPI)
- **File**: `backend/server.py`
- **Database**: SQLite for persistent post storage
- **AI**: Anthropic Claude API for comment generation
- **Key APIs**:
  - `POST /api/posts/submit` - Process Reddit URLs
  - `GET /api/posts/{post_id}` - Get mixed comments for gameplay
  - `GET /api/posts` - List all processed posts

### Frontend (SvelteKit) 
- **Main Game**: `frontend/src/routes/+page.svelte`
- **Submit Page**: `frontend/src/routes/submit/+page.svelte`
- **Styling**: `frontend/src/app.css` with extensive glitch effects
- **Features**: Character replacement glitching, font transitions, cyberpunk aesthetics

## Current Game Mechanics
1. **Fixed Balance**: Exactly 8 human comments + 8 AI comments = 16 total
2. **Tree Structure**: Maintains Reddit's nested comment structure (parents/replies)
3. **Scoring**: Live stats showing correct/incorrect guesses
4. **Visual Effects**: AI comments revealed with username changing to "REPLICANT" and text glitching

## Comment Generation System Evolution

### Phase 1: Basic Generation
Initially used simple prompts to generate AI comments, but they were too obviously artificial.

### Phase 2: Archetype System (Current)
Created sophisticated archetype system to generate more realistic comments:

**File**: `backend/src/comment_archetypes.py`
- **18 Different Archetypes** across 4 categories:
  - `amitheasshole`: `harsh_judge`, `nuanced_analyzer`, `personal_boundary_expert`, `devils_advocate`
  - `relationship_advice`: `breakup_advocate`, `therapist_voice`, `personal_experience_sharer`, `optimistic_fixer`
  - `unpopularopinion`: `agreeable_ally`, `fact_checker`, `cultural_critic`, `moderate_voice`
  - `generic`: `casual_reactor`, `story_teller`, `supportive_friend`, `one_liner_comedian`, `practical_advisor`, `question_asker`

**How it works**:
1. AI analyzes the specific Reddit post
2. Selects 4-6 appropriate archetypes for that post's context
3. Generates individual comments using different archetypes
4. Each comment has a distinct personality and approach

### Key Functions:
```python
# Select appropriate archetypes for a specific post
get_appropriate_archetypes(post_title, post_content, subreddit, anthropic_client)

# Build complete prompt combining context + archetype
build_full_prompt(archetype_key, subreddit, post_title, post_content, real_comment_examples)

# Generate single comment with specific archetype
generate_single_ai_comment(post_title, post_content, subreddit, real_comments, archetype_key, anthropic_client)
```

## Current Critical Problem: AI Comments Too Obvious

### Analysis of Recent Output
Looking at a recent generation for "Video games are good for you" post, AI comments have several telltale signs:

**Example AI Comment (obvious giveaway)**:
> "I agree with a lot of what you're saying, but I think we need to be more nuanced about this. Video games can absolutely provide those benefits you mentioned - the problem-solving, social connections, and stress relief are all real positives. But like any form of entertainment or hobby, the impact really depends on how they're used..."

**Example Human Comment (natural)**:
> "Not unpopular dude"

### Specific Issues Identified:

#### 1. Length Disparity
- **AI**: 100-200+ words, multiple paragraphs
- **Human**: 5-50 words, mostly single sentences
- **Problem**: AI writes essays while humans drop quick reactions

#### 2. Repetitive Patterns
- **"I agree with a lot of what you're saying, but..."** (appeared twice)
- **"I think we need to be more nuanced"**
- **"The key is moderation/balance"**
- **Academic hedge phrases**: "I think," "probably," "might be"

#### 3. Tone & Language
- **AI**: "nuanced," "legitimate," "cognitive benefits," "meta-analysis"
- **Human**: "dude," "literally," "basement dweller," casual abbreviations
- **AI**: Perfect grammar, formal structure
- **Human**: Typos ("didn't a semester"), run-on sentences, casual formatting

#### 4. Content Approach
- **AI**: Tries to address multiple aspects comprehensively, diplomatic
- **Human**: Focuses on one specific point, more direct and opinionated

#### 5. Missing Reddit Culture
- **AI**: No Reddit-specific slang, memes, or vernacular
- **Human**: Uses "fr," "ngl," "based," platform-specific language

## Proposed Solution: Archetype Length Weighting

### The Problem with Current Approach
Many archetypes naturally lead to long, balanced responses:
- `nuanced_analyzer` → Complex breakdowns
- `moderate_voice` → Diplomatic middle ground
- `cultural_critic` → Societal analysis

The AI archetype selection seems to bias toward "thoughtful" responses for serious topics.

### Proposed Solution: Structured Length Distribution

Instead of random casual/formal behavior, implement weighted archetype selection:

#### Length Categories:
1. **Brief (1-30 words, 60% of comments)**:
   - `casual_reactor`: "lmao this is wild"
   - `one_liner_comedian`: Quick jokes/witty observations
   - `question_asker`: "wait, did he actually say that?"

2. **Medium (30-100 words, 30% of comments)**:
   - `story_teller`: Brief personal anecdotes
   - `practical_advisor`: Short actionable advice
   - `harsh_judge` (AITA): "YTA. You're being selfish and you know it."
   - `agreeable_ally`: "FINALLY someone said it!"

3. **Long (100+ words, 10% of comments)**:
   - `nuanced_analyzer`: Complex breakdowns (but constrained)
   - `cultural_critic`: Societal analysis
   - `therapist_voice`: Detailed psychological takes

#### Implementation Strategy:
```python
# Weight distribution in get_appropriate_archetypes()
brief_weight = 0.6    # 60% brief responses
medium_weight = 0.3   # 30% medium responses  
long_weight = 0.1     # 10% long responses

# Force distribution when selecting archetypes:
selected_archetypes = [
    3-4 brief archetypes,    # Quick reactions, one-liners
    1-2 medium archetypes,   # Focused responses
    0-1 long archetype       # Occasional detailed analysis
]
```

#### Add Length Constraints to Prompts:
```python
length_hints = {
    'brief': "Keep response under 30 words. Be direct and casual.",
    'medium': "Keep response 30-80 words. Focus on one main point.",
    'long': "Can be longer but don't exceed 150 words. Be comprehensive but concise."
}
```

## Recent Technical Fixes Applied

### Issue 1: Wrong Comment Counts
**Problem**: Getting 20 comments instead of 16
**Cause**: Taking 8 top-level comments but including all their nested replies
**Fix**: Flatten all comments first, take exactly 8, then rebuild tree structure

### Issue 2: Duplicate Comments  
**Problem**: Same comments appearing in multiple places
**Cause**: Comments in both main list and nested replies
**Fix**: Use tree filtering to maintain structure without duplication

### Issue 3: Missing AI Reply Structure
**Problem**: All AI comments were top-level
**Fix**: Generate mix of top-level (4) and reply comments (4) to maintain natural conversation flow

### Issue 4: Inconsistent AI Count
**Problem**: Sometimes getting 7 AI instead of 8
**Cause**: AI generation failures not being compensated
**Fix**: Added fallback logic to ensure exactly 8 AI comments always generated

```python
# Current logic in server.py
total_ai_generated = len(ai_top_level) + len(ai_replies)
if total_ai_generated < target_ai_count:
    additional_needed = target_ai_count - total_ai_generated
    additional_ai = generate_ai_comments_with_archetypes(...)
    ai_top_level.extend(additional_ai)
```

## File Structure Details

### Backend Files
```
backend/
├── server.py                           # Main FastAPI application
├── .env                               # ANTHROPIC_API_KEY configuration
├── src/
│   ├── comment_archetypes.py          # 18 archetype definitions
│   ├── generate_mixed_comments.py     # AI comment generation logic
│   ├── reddit_parser.py              # Reddit JSON parsing
│   ├── reddit_fetcher.py             # Reddit API fetching
│   └── database.py                   # SQLite operations
└── requirements.txt                   # Python dependencies
```

### Frontend Files
```
frontend/
├── src/
│   ├── routes/
│   │   ├── +page.svelte              # Main game interface
│   │   └── submit/+page.svelte       # Reddit URL submission
│   ├── app.css                       # Cyberpunk styling & glitch effects
│   └── app.html                      # Base HTML template
├── package.json                      # Node.js dependencies
└── vite.config.js                    # Build configuration
```

## Key Code Sections

### Archetype System Core
```python
# comment_archetypes.py
ARCHETYPES = {
    'unpopularopinion': {
        'agreeable_ally': {
            'description': 'Enthusiastically agrees with controversial takes',
            'prompt': '''COMMENT STYLE: You enthusiastically support the unpopular opinion...
- Use phrases like "FINALLY someone said it!"
- Share your own frustrations about the topic...'''
        }
    }
}

def build_full_prompt(archetype_key, subreddit, post_title, post_content, real_comment_examples):
    archetype = get_archetype_prompt(archetype_key)
    context = COMMON_CONTEXT_TEMPLATE.format(...)
    return context + archetype['prompt'] + COMMON_REQUIREMENTS
```

### Comment Generation Flow
```python
# generate_mixed_comments.py
def generate_ai_comments_with_archetypes(post_title, post_content, subreddit, real_comments, num_to_generate, anthropic_client):
    # Step 1: Get appropriate archetypes for this post
    appropriate_archetypes = get_appropriate_archetypes(post_title, post_content, subreddit, anthropic_client)
    
    # Step 2: Generate individual comments using random archetypes
    for i in range(num_to_generate):
        selected_archetype = random.choice(appropriate_archetypes)
        comment = generate_single_ai_comment(..., archetype_key=selected_archetype, ...)
```

### Frontend Glitch Effects
```javascript
// +page.svelte - Character replacement glitching
function startTextGlitch(commentId, originalText) {
    // Randomly replace 1-4% of non-whitespace characters
    const randomPercentage = 0.01 + (Math.random() * 0.03);
    const numToGlitch = Math.floor(nonWhitespaceIndices.length * randomPercentage);
    
    // Replace with glitch characters
    indicesToGlitch.forEach(index => {
        textArray[index] = glitchChars[Math.floor(Math.random() * glitchChars.length)];
    });
}
```

## UI/UX Features Implemented

### Glitch Effects System
1. **Text Character Replacement**: Random characters replaced with glitch symbols
2. **Font Transitions**: Smooth transition from proportional to monospace during glitching
3. **CSS Animations**: Clipping paths, movement, and color effects
4. **Timing Coordination**: 800-1400ms intervals for character replacement

### Game Interface
1. **Fixed Toolbar**: Live statistics showing correct/incorrect/remaining guesses
2. **Reveal Animation**: Username fades to "REPLICANT" with glitch effect
3. **Feedback Messages**: 
   - Correct: "✅ Replicant identified" / "Reddit origin confirmed"
   - Wrong: "❌ Detection failed. This was a replicant/is from Reddit"

### Page Transitions
- **View Transition API**: Smooth transitions between submit and game pages
- **Fade Effects**: Dialog animations and route changes

## Environment & Setup

### Required Environment Variables
```bash
# .env file
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### Development Commands
```bash
# Backend
cd backend
python -m uvicorn server:app --reload --port 8000

# Frontend  
cd frontend
npm install
npm run dev
```

### Target Subreddits
Focus on these 3 subreddits for archetype system:
- `r/AmITheAsshole` - Moral judgment discussions
- `r/relationship_advice` - Personal relationship problems
- `r/unpopularopinion` - Controversial takes and debates

## Current Status & Next Steps

### Completed ✅
1. Basic Reddit comment fetching and parsing
2. AI comment generation with Claude API
3. Sophisticated archetype system (18 personality types)
4. Balanced 8+8 comment system with proper tree structure
5. Cyberpunk UI with glitch effects and animations
6. Game mechanics with live scoring

### In Progress 🔄
1. **Archetype Length Weighting System** - Main focus to improve AI comment realism
2. **Analysis of AI comment obviousness patterns**

### Next Priority Tasks
1. **Implement length-based archetype weighting** (60% brief, 30% medium, 10% long)
2. **Add length constraints to archetype prompts**
3. **Test with real Reddit posts** to verify improved realism
4. **Iterate on archetype selection logic** based on results
5. **Consider adding casual language patterns** and occasional typos

### Future Enhancements
1. **More subreddit-specific archetypes**
2. **Better casual language integration** 
3. **Advanced scoring system** with difficulty levels
4. **Comment voting simulation** (upvotes/downvotes)
5. **Leaderboard system** for user performance

## Testing Strategy
1. **Manual Testing**: Submit posts from target subreddits and analyze AI comment quality
2. **A/B Testing**: Compare current vs length-weighted archetype systems
3. **User Testing**: Have real users try to identify AI comments
4. **Iteration**: Adjust archetype weights based on detection rates

## Known Limitations
1. **API Rate Limits**: Anthropic API has usage limits
2. **Generation Failures**: Sometimes AI fails to generate valid JSON responses
3. **Reddit API**: Currently using manual URL submission rather than direct Reddit API
4. **Single Language**: English only
5. **Limited Subreddits**: Focused on 3 specific subreddits

This context should be sufficient to resume development work on the archetype length weighting system to make AI comments less obviously artificial.