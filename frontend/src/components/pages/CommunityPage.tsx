import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { AuthSession } from '../AuthScreens';
import {
  createCommunityComment,
  createCommunityPost,
  getCommunityComments,
  getCommunityPosts,
  toggleCommunityBookmark,
  toggleCommunityLike,
  type CommunityComment,
  type CommunityPost,
  type CommunityPreviewType,
  type CommunitySort,
  type CommunityTab,
} from '../../community/communityClient';
import './CommunityPage.css';

interface CommunityPageProps {
  apiBaseUrl: string;
  authSession: AuthSession;
  onAuthAction: () => void;
}

type CommunitySection =
  | 'feed'
  | 'trending'
  | 'following'
  | 'badges'
  | 'clubs'
  | 'favorites'
  | 'my-posts'
  | 'notifications'
  | 'settings';

const stories = [
  { id: 'add', name: '新增限時', isAdd: true },
  { id: 'leo', name: 'Leo T.', tone: 'aqua' },
  { id: 'dr-mu', name: 'Dr. Mu', tone: 'rose' },
  { id: 'xiao', name: 'Xiao Cai', tone: 'amber' },
  { id: 'pool', name: '台北球館', tone: 'blue' },
  { id: 'rex', name: 'RexChen', tone: 'green' },
  { id: 'soul', name: '9Ball Soul', tone: 'rose' },
  { id: 'break', name: 'BreakMast...', tone: 'amber' },
  { id: 'cue', name: 'CueQueen', tone: 'indigo' },
  { id: 'pro', name: 'ProShot', tone: 'aqua' },
];

const sectionItems: Array<{ id: CommunitySection; label: string }> = [
  { id: 'feed', label: '動態牆' },
  { id: 'trending', label: '熱門' },
  { id: 'following', label: '追蹤中' },
  { id: 'badges', label: '徽章' },
  { id: 'clubs', label: '球會' },
  { id: 'my-posts', label: '我的貼文' },
  { id: 'favorites', label: '我的收藏' },
  { id: 'notifications', label: '通知' },
  { id: 'settings', label: '設定' },
];

const feedTabs: Array<{ label: string; value: CommunityTab }> = [
  { label: '全部', value: 'all' },
  { label: '探索', value: 'explore' },
  { label: '追蹤中', value: 'following' },
];

const sortOptions: Array<{ label: string; value: CommunitySort }> = [
  { label: '最新', value: 'latest' },
  { label: '熱門', value: 'popular' },
  { label: '最多留言', value: 'comments' },
];

const previewOptions: Array<{ label: string; value: CommunityPreviewType }> = [
  { label: '球桌路線', value: 'pool-table' },
  { label: '薄球攻防', value: 'pool-table-alt' },
  { label: '姿態分析', value: 'pose-analysis' },
  { label: '數據圖表', value: 'stats' },
];

const hotTopics = ['AI 路線推薦', '安全球選擇', '開球控球', '母球走位'];
const clubs = ['CueVex 台北球會', '9 Ball 練習團', '週末撞球聯盟'];
const events = ['10 球挑戰賽', '安全球工作坊', '走位專項練習'];

const profileStats = [
  { label: '貼文', value: '6' },
  { label: '獲讚', value: '128' },
  { label: '追蹤中', value: '42' },
];

const profilePosts = [
  {
    id: 'profile-1',
    title: '九號球清台練習',
    description: '連續三局清台後，CueVex 建議把母球停點再往右側半顆球。',
    tone: 'aqua',
    preview: 'pool-table' as CommunityPreviewType,
    likes: 38,
    comments: 6,
  },
  {
    id: 'profile-2',
    title: '薄球攻防選擇',
    description: '這顆球攻擊成功率偏低，改用安全球能把對手留在長台。',
    tone: 'rose',
    preview: 'pool-table-alt' as CommunityPreviewType,
    likes: 24,
    comments: 3,
  },
  {
    id: 'profile-3',
    title: '出桿姿態校正',
    description: '肩線偏移在最後 0.2 秒最明顯，下一輪會先修正節奏。',
    tone: 'blue',
    preview: 'pose-analysis' as CommunityPreviewType,
    likes: 41,
    comments: 9,
  },
  {
    id: 'profile-4',
    title: '開球數據回顧',
    description: '本週開球進球率 72%，母球留在中央區域的比例提升到 58%。',
    tone: 'green',
    preview: 'stats' as CommunityPreviewType,
    likes: 19,
    comments: 2,
  },
  {
    id: 'profile-5',
    title: '安全球練習',
    description: '把目標球貼近短庫後，CueVex 判定防守收益比直接進攻更高。',
    tone: 'indigo',
    preview: 'pool-table-alt' as CommunityPreviewType,
    likes: 32,
    comments: 5,
  },
  {
    id: 'profile-6',
    title: '訓練週報',
    description: '本週完成 6 小時練習，平均入袋率 68%，最佳連續成功 12 球。',
    tone: 'amber',
    preview: 'stats' as CommunityPreviewType,
    likes: 57,
    comments: 11,
  },
];

const ballLayouts = {
  default: [
    { x: 55, y: 35, color: '#f6c84c', label: '1' },
    { x: 70, y: 55, color: '#3b82f6', label: '2' },
    { x: 40, y: 60, color: '#ef4444', label: '3' },
    { x: 25, y: 40, color: '#9b5de5', label: '4' },
    { x: 80, y: 30, color: '#f97316', label: '5' },
    { x: 15, y: 65, color: '#22c55e', label: '6' },
    { x: 35, y: 25, color: '#1f2937', label: '8' },
    { x: 60, y: 70, color: '#a34224', label: '7' },
    { x: 85, y: 65, color: '#ffe45c', label: '9' },
  ],
  alt: [
    { x: 20, y: 50, color: '#ffffff', label: '' },
    { x: 75, y: 45, color: '#f6c84c', label: '9' },
    { x: 50, y: 30, color: '#3b82f6', label: '2' },
    { x: 60, y: 65, color: '#ef4444', label: '3' },
    { x: 35, y: 70, color: '#22c55e', label: '6' },
  ],
};

const formatPostTime = (value: string): string => {
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return value;
  const diffMinutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60000));
  if (diffMinutes < 1) return '剛剛';
  if (diffMinutes < 60) return `${diffMinutes} 分鐘前`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} 小時前`;
  return `${Math.floor(diffHours / 24)} 天前`;
};

function Avatar({ tone = 'aqua', size = 'medium' }: { tone?: string; size?: 'small' | 'medium' | 'large' }) {
  return (
    <span className={`community-avatar ${tone} ${size}`} aria-hidden="true">
      <span />
    </span>
  );
}

function PoolTablePreview({ variant = 'default' }: { variant?: 'default' | 'alt' }) {
  const balls = variant === 'default' ? ballLayouts.default : ballLayouts.alt;
  const routes =
    variant === 'default'
      ? [
          { x1: 40, y1: 60, x2: 55, y2: 35, dashed: false },
          { x1: 55, y1: 35, x2: 70, y2: 55, dashed: true },
          { x1: 70, y1: 55, x2: 86, y2: 65, dashed: true },
        ]
      : [
          { x1: 20, y1: 50, x2: 75, y2: 45, dashed: true },
          { x1: 75, y1: 45, x2: 94, y2: 50, dashed: false },
        ];

  return (
    <div className="community-table-preview">
      <span className="community-table-marker top" />
      <span className="community-table-marker bottom" />
      <div className="community-table-felt" />
      <svg className="community-route-layer" viewBox="0 0 100 100" preserveAspectRatio="none">
        {routes.map((route, index) => (
          <line
            key={index}
            x1={route.x1}
            y1={route.y1}
            x2={route.x2}
            y2={route.y2}
            stroke="currentColor"
            strokeWidth="0.75"
            strokeDasharray={route.dashed ? '2.4 1.8' : undefined}
          />
        ))}
      </svg>
      {balls.map((ball) => (
        <span
          className="community-ball"
          key={`${ball.x}-${ball.y}-${ball.label}`}
          style={{ left: `${ball.x}%`, top: `${ball.y}%`, background: ball.color }}
        >
          {ball.label}
        </span>
      ))}
      <div className="community-preview-metrics">
        <span>
          進攻成功率 <strong>87%</strong>
        </span>
        <span>
          走位穩定度 <strong>91%</strong>
        </span>
      </div>
    </div>
  );
}

function PoseAnalysisPreview() {
  const joints = [
    { cx: 100, cy: 20 },
    { cx: 100, cy: 35 },
    { cx: 100, cy: 60 },
    { cx: 50, cy: 50 },
    { cx: 155, cy: 28 },
    { cx: 84, cy: 82 },
    { cx: 116, cy: 82 },
  ];

  return (
    <div className="community-pose-preview">
      <svg viewBox="0 0 200 100" aria-hidden="true">
        <line x1="100" y1="20" x2="100" y2="60" />
        <line x1="100" y1="35" x2="50" y2="50" />
        <line x1="100" y1="35" x2="155" y2="28" />
        <line x1="100" y1="60" x2="84" y2="82" />
        <line x1="100" y1="60" x2="116" y2="82" />
        <line className="cue" x1="30" y1="55" x2="180" y2="25" />
        {joints.map((joint) => (
          <circle key={`${joint.cx}-${joint.cy}`} cx={joint.cx} cy={joint.cy} r="4" />
        ))}
        <text x="126" y="42">15 deg</text>
      </svg>
      <div className="community-preview-metrics left">
        <span>
          身體穩定度 <strong>82%</strong>
        </span>
        <span>
          出桿直線度 <strong>89%</strong>
        </span>
      </div>
    </div>
  );
}

function StatsPreview() {
  return (
    <div className="community-stats-preview">
      <div className="community-mini-chart">
        {[45, 68, 52, 78, 64, 71, 58, 82, 64].map((height, index) => (
          <span key={index} style={{ height: `${height}%` }} />
        ))}
      </div>
      <div className="community-mini-summary">
        <PoolTablePreview variant="alt" />
        <span>開球速度 28 mph</span>
        <span>入袋率 64%</span>
        <span>走位評級 B+</span>
      </div>
    </div>
  );
}

function Preview({ type }: { type: CommunityPreviewType }) {
  if (type === 'pool-table') return <PoolTablePreview />;
  if (type === 'pool-table-alt') return <PoolTablePreview variant="alt" />;
  if (type === 'pose-analysis') return <PoseAnalysisPreview />;
  return <StatsPreview />;
}

function CommunityLeftNav({
  activeSection,
  onSelect,
}: {
  activeSection: CommunitySection;
  onSelect: (section: CommunitySection) => void;
}) {
  return (
    <aside className="community-left-nav">
      {sectionItems.map((item, index) => (
        <React.Fragment key={item.id}>
          {index === 5 && <div className="community-left-separator" />}
          <button
            className={`community-left-item ${activeSection === item.id ? 'active' : ''}`}
            type="button"
            onClick={() => onSelect(item.id)}
          >
            {item.label}
          </button>
        </React.Fragment>
      ))}
    </aside>
  );
}

function StoryCarousel({ onAddStory }: { onAddStory: () => void }) {
  return (
    <section className="community-panel community-stories" aria-label="限時動態">
      <h2>限時動態</h2>
      <div className="community-story-row">
        {stories.map((story) => (
          <button
            className="community-story"
            key={story.id}
            type="button"
            onClick={story.isAdd ? onAddStory : undefined}
          >
            {story.isAdd ? <span className="community-add-story">+</span> : <Avatar tone={story.tone} size="large" />}
            <span>{story.name}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

function PostComposer({
  disabled,
  isOpen,
  isSubmitting,
  onLogin,
  onSubmit,
}: {
  disabled: boolean;
  isOpen: boolean;
  isSubmitting: boolean;
  onLogin: () => void;
  onSubmit: (payload: { title: string; body: string; previewType: CommunityPreviewType }) => Promise<void>;
}) {
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [previewType, setPreviewType] = useState<CommunityPreviewType>('pool-table');
  const canSubmit = title.trim().length > 0 && body.trim().length > 0 && !isSubmitting;

  if (disabled) {
    return (
      <section className="community-panel community-composer community-login-prompt">
        <div>
          <h2>登入後發布動態</h2>
          <p>分享路線判斷、練習紀錄或 AI 分析心得。</p>
        </div>
        <button type="button" onClick={onLogin}>
          登入
        </button>
      </section>
    );
  }

  if (!isOpen) return null;

  return (
    <form
      className="community-panel community-composer"
      onSubmit={(event) => {
        event.preventDefault();
        if (!canSubmit) return;
        onSubmit({ title: title.trim(), body: body.trim(), previewType }).then(() => {
          setTitle('');
          setBody('');
          setPreviewType('pool-table');
        });
      }}
    >
      <input value={title} maxLength={80} placeholder="貼文標題" onChange={(event) => setTitle(event.target.value)} />
      <textarea
        value={body}
        maxLength={800}
        placeholder="分享你的練習重點、比賽心得或路線選擇"
        rows={3}
        onChange={(event) => setBody(event.target.value)}
      />
      <div className="community-composer-actions">
        <select
          value={previewType}
          aria-label="預覽類型"
          onChange={(event) => setPreviewType(event.target.value as CommunityPreviewType)}
        >
          {previewOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <button type="submit" disabled={!canSubmit}>
          {isSubmitting ? '發布中...' : '發布'}
        </button>
      </div>
    </form>
  );
}

function CommentsPanel({
  apiBaseUrl,
  post,
  token,
  onLogin,
  onPostUpdate,
}: {
  apiBaseUrl: string;
  post: CommunityPost;
  token?: string;
  onLogin: () => void;
  onPostUpdate: (post: CommunityPost) => void;
}) {
  const [comments, setComments] = useState<CommunityComment[]>([]);
  const [body, setBody] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    getCommunityComments(apiBaseUrl, post.id)
      .then((response) => {
        if (isMounted) setComments(response.comments);
      })
      .catch(() => {
        if (isMounted) setComments([]);
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [apiBaseUrl, post.id]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) {
      onLogin();
      return;
    }
    const nextBody = body.trim();
    if (!nextBody || isSubmitting) return;
    setIsSubmitting(true);
    try {
      const response = await createCommunityComment(apiBaseUrl, token, post.id, nextBody);
      setComments((current) => [...current, response.comment]);
      onPostUpdate(response.post);
      setBody('');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="community-comments">
      {isLoading ? (
        <div className="community-comments-empty">留言載入中...</div>
      ) : comments.length === 0 ? (
        <div className="community-comments-empty">尚無留言</div>
      ) : (
        comments.map((comment) => (
          <article className="community-comment" key={comment.id}>
            <strong>{comment.author_name}</strong>
            <span>{formatPostTime(comment.created_at)}</span>
            <p>{comment.body}</p>
          </article>
        ))
      )}
      <form className="community-comment-form" onSubmit={handleSubmit}>
        <input
          value={body}
          maxLength={500}
          placeholder={token ? '新增留言' : '登入後留言'}
          onChange={(event) => setBody(event.target.value)}
        />
        <button type="submit" disabled={isSubmitting || (!token && body.trim().length === 0)}>
          {token ? '送出' : '登入'}
        </button>
      </form>
    </section>
  );
}

function PostCard({
  apiBaseUrl,
  post,
  token,
  onLogin,
  onOptimisticUpdate,
  onPostUpdate,
  onActionError,
  onShare,
}: {
  apiBaseUrl: string;
  post: CommunityPost;
  token?: string;
  onLogin: () => void;
  onOptimisticUpdate: (post: CommunityPost) => void;
  onPostUpdate: (post: CommunityPost) => void;
  onActionError: () => void;
  onShare: (post: CommunityPost) => void;
}) {
  const [showComments, setShowComments] = useState(false);

  const requireLogin = (): boolean => {
    if (token) return true;
    onLogin();
    return false;
  };

  const handleLike = async () => {
    if (!requireLogin() || !token) return;
    const previous = post;
    const optimistic = {
      ...post,
      liked_by_me: !post.liked_by_me,
      likes: post.liked_by_me ? Math.max(0, post.likes - 1) : post.likes + 1,
    };
    onOptimisticUpdate(optimistic);
    try {
      onPostUpdate(await toggleCommunityLike(apiBaseUrl, token, post.id));
    } catch {
      onPostUpdate(previous);
      onActionError();
    }
  };

  const handleBookmark = async () => {
    if (!requireLogin() || !token) return;
    const previous = post;
    onOptimisticUpdate({ ...post, bookmarked_by_me: !post.bookmarked_by_me });
    try {
      onPostUpdate(await toggleCommunityBookmark(apiBaseUrl, token, post.id));
    } catch {
      onPostUpdate(previous);
      onActionError();
    }
  };

  const toggleComments = () => setShowComments((value) => !value);

  return (
    <article className="community-post" id={`community-post-${post.id}`} onClick={toggleComments}>
      <header className="community-post-header">
        <Avatar tone={post.tone} />
        <div>
          <div className="community-post-author">
            <strong>{post.author_name}</strong>
            <span>{post.badge}</span>
          </div>
          <time>{formatPostTime(post.created_at)}</time>
        </div>
        <button
          className="community-icon-button"
          type="button"
          aria-label="更多操作"
          onClick={(event) => event.stopPropagation()}
        >
          ...
        </button>
      </header>
      <h2>{post.title}</h2>
      <p>{post.body}</p>
      <Preview type={post.preview_type} />
      <footer className="community-post-actions" onClick={(event) => event.stopPropagation()}>
        <button className={post.liked_by_me ? 'active danger' : ''} type="button" onClick={handleLike}>
          <span className="community-action-icon like" aria-hidden="true" />
          {post.likes}
        </button>
        <button type="button" onClick={toggleComments}>
          <span className="community-action-icon comment" aria-hidden="true" />
          {post.comments}
        </button>
        <button type="button" onClick={() => onShare(post)}>
          <span className="community-action-icon share" aria-hidden="true" />
          分享
        </button>
        <button className={post.bookmarked_by_me ? 'active' : ''} type="button" onClick={handleBookmark}>
          <span className="community-action-icon save" aria-hidden="true" />
          收藏
        </button>
      </footer>
      {showComments && (
        <CommentsPanel
          apiBaseUrl={apiBaseUrl}
          post={post}
          token={token}
          onLogin={onLogin}
          onPostUpdate={onPostUpdate}
        />
      )}
    </article>
  );
}

function SkeletonPanel({ title, action, rows = 3 }: { title: string; action: string; rows?: number }) {
  return (
    <section className="community-panel community-skeleton-panel">
      <div className="community-panel-heading">
        <h2>{title}</h2>
        <button type="button">{action}</button>
      </div>
      {Array.from({ length: rows }).map((_, index) => (
        <div className="community-skeleton-row" key={index}>
          <span />
          <div>
            <strong />
            <em />
          </div>
        </div>
      ))}
    </section>
  );
}

function SidePanel({
  totalPosts,
  onTopicClick,
  onClubClick,
  onEventClick,
}: {
  totalPosts: number;
  onTopicClick: (topic: string) => void;
  onClubClick: (club: string) => void;
  onEventClick: (event: string) => void;
}) {
  return (
    <aside className="community-side">
      <section className="community-panel">
        <div className="community-panel-heading">
          <h2>熱門話題</h2>
          <button type="button" onClick={() => onTopicClick('所有話題')}>
            查看全部
          </button>
        </div>
        {hotTopics.map((item, index) => (
          <button className="community-topic" key={item} type="button" onClick={() => onTopicClick(item)}>
            <span>{index + 1}</span>
            <strong>{item}</strong>
          </button>
        ))}
      </section>
      <section className="community-panel">
        <div className="community-panel-heading">
          <h2>推薦球會</h2>
          <button type="button" onClick={() => onClubClick('所有球會')}>
            瀏覽
          </button>
        </div>
        {clubs.map((item) => (
          <button className="community-club" key={item} type="button" onClick={() => onClubClick(item)}>
            <Avatar tone="green" size="small" />
            <span>{item}</span>
          </button>
        ))}
      </section>
      <section className="community-panel community-event">
        <div className="community-panel-heading">
          <h2>本週挑戰</h2>
          <button type="button" onClick={() => onEventClick('所有活動')}>
            查看全部
          </button>
        </div>
        {events.map((item) => (
          <button className="community-event-row" key={item} type="button" onClick={() => onEventClick(item)}>
            <span />
            <strong>{item}</strong>
          </button>
        ))}
        <p>目前共有 {totalPosts} 則社群貼文可瀏覽。</p>
      </section>
    </aside>
  );
}

function ProfilePostCard({ post }: { post: (typeof profilePosts)[number] }) {
  return (
    <article className="community-profile-post">
      <header className="community-profile-post-header">
        <Avatar tone={post.tone} />
        <div>
          <strong>@123</strong>
          <span>{post.title}</span>
        </div>
      </header>

      <div className="community-profile-post-photo">
        <Preview type={post.preview} />
      </div>

      <footer className="community-profile-post-footer">
        <div className="community-profile-post-actions">
          <button type="button" aria-label="按讚">
            <span className="community-action-icon like" aria-hidden="true" />
            {post.likes}
          </button>
          <button type="button" aria-label="留言">
            <span className="community-action-icon comment" aria-hidden="true" />
            {post.comments}
          </button>
          <button type="button" aria-label="分享">
            <span className="community-action-icon share" aria-hidden="true" />
            分享
          </button>
          <button className="save" type="button" aria-label="收藏">
            <span className="community-action-icon save" aria-hidden="true" />
          </button>
        </div>
        <p>{post.description}</p>
      </footer>
    </article>
  );
}

function CommunityProfilePage() {
  return (
    <main className="community-profile-main">
      <section className="community-profile-hero">
        <Avatar tone="aqua" size="large" />
        <div className="community-profile-meta">
          <h1>@123</h1>
          <div className="community-profile-stats" aria-label="個人社群統計">
            {profileStats.map((item) => (
              <div key={item.label}>
                <strong>{item.value}</strong>
                <span>{item.label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="community-profile-posts" aria-label="我的貼文列表">
        {profilePosts.map((post) => (
          <ProfilePostCard key={post.id} post={post} />
        ))}
      </section>
    </main>
  );
}

const CommunityPage: React.FC<CommunityPageProps> = ({ apiBaseUrl, authSession, onAuthAction }) => {
  const token = authSession.type === 'user' ? authSession.token : undefined;
  const composerRef = useRef<HTMLDivElement>(null);
  const [activeSection, setActiveSection] = useState<CommunitySection>('feed');
  const [activeTab, setActiveTab] = useState<CommunityTab>('all');
  const [sortBy, setSortBy] = useState<CommunitySort>('latest');
  const [posts, setPosts] = useState<CommunityPost[]>([]);
  const [totalPosts, setTotalPosts] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmittingPost, setIsSubmittingPost] = useState(false);
  const [isComposerOpen, setIsComposerOpen] = useState(false);
  const [message, setMessage] = useState('');

  const totalLikes = useMemo(() => posts.reduce((total, post) => total + post.likes, 0), [posts]);

  const updatePost = (nextPost: CommunityPost) => {
    setPosts((current) => current.map((post) => (post.id === nextPost.id ? nextPost : post)));
  };

  const showMessage = (nextMessage: string) => {
    setMessage(nextMessage);
    window.setTimeout(() => setMessage(''), 2400);
  };

  const openComposer = () => {
    if (!token) {
      onAuthAction();
      return;
    }
    setIsComposerOpen(true);
    window.setTimeout(() => composerRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' }), 0);
  };

  const handleSectionSelect = (section: CommunitySection) => {
    setActiveSection(section);
    if (section === 'feed') setActiveTab('all');
    if (section === 'trending') {
      setActiveTab('explore');
      setSortBy('popular');
    }
    if (section === 'following') setActiveTab('following');
    if (section === 'my-posts') return;
    if (section !== 'feed' && section !== 'trending' && section !== 'following') {
      showMessage(`${sectionItems.find((item) => item.id === section)?.label || '此'}頁面將在下一版接入。`);
    }
  };

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    getCommunityPosts(apiBaseUrl, { tab: activeTab, sort: sortBy }, token)
      .then((response) => {
        if (!isMounted) return;
        setPosts(response.posts);
        setTotalPosts(response.total);
      })
      .catch(() => {
        if (isMounted) showMessage('社群動態載入失敗。');
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [activeTab, apiBaseUrl, sortBy, token]);

  const handleCreatePost = async (payload: {
    title: string;
    body: string;
    previewType: CommunityPreviewType;
  }) => {
    if (!token) {
      onAuthAction();
      return;
    }

    setIsSubmittingPost(true);
    try {
      const post = await createCommunityPost(apiBaseUrl, token, {
        title: payload.title,
        body: payload.body,
        preview_type: payload.previewType,
      });
      setPosts((current) => [post, ...current]);
      setTotalPosts((current) => current + 1);
      setIsComposerOpen(false);
      showMessage('貼文已發布。');
    } catch {
      showMessage('貼文發布失敗。');
    } finally {
      setIsSubmittingPost(false);
    }
  };

  const handleShare = (post: CommunityPost) => {
    const url = `${window.location.origin}${window.location.pathname}#community-post-${post.id}`;
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(url).then(
        () => showMessage('貼文連結已複製。'),
        () => showMessage(`分享連結：${url}`),
      );
      return;
    }
    showMessage(`分享連結：${url}`);
  };

  return (
    <div className="community-page">
      <CommunityLeftNav activeSection={activeSection} onSelect={handleSectionSelect} />

      {activeSection === 'my-posts' ? (
        <CommunityProfilePage />
      ) : (
        <main className="community-feed">
          <StoryCarousel onAddStory={openComposer} />
          <div ref={composerRef}>
            <PostComposer
              disabled={!token}
              isOpen={isComposerOpen}
              isSubmitting={isSubmittingPost}
              onLogin={onAuthAction}
              onSubmit={handleCreatePost}
            />
          </div>
          <div className="community-feed-tools">
            <div className="community-tabs" role="tablist" aria-label="動態分類">
              {feedTabs.map((tab) => (
                <button
                  className={activeTab === tab.value ? 'active' : ''}
                  key={tab.value}
                  type="button"
                  onClick={() => setActiveTab(tab.value)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <select
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value as CommunitySort)}
              aria-label="排序"
            >
              {sortOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          {message && <div className="community-status">{message}</div>}
          <div className="community-feed-summary" aria-label="社群統計">
            <span>{totalPosts} 則貼文</span>
            <span>{totalLikes} 個讚</span>
          </div>
          <div className="community-post-list">
            {isLoading ? (
              <SkeletonPanel title="動態載入中" action="請稍候" rows={4} />
            ) : posts.length === 0 ? (
              <div className="community-status">尚無符合條件的貼文。</div>
            ) : (
              posts.map((post) => (
                <PostCard
                  apiBaseUrl={apiBaseUrl}
                  key={post.id}
                  post={post}
                  token={token}
                  onLogin={onAuthAction}
                  onOptimisticUpdate={updatePost}
                  onPostUpdate={updatePost}
                  onActionError={() => showMessage('操作失敗，請稍後再試。')}
                  onShare={handleShare}
                />
              ))
            )}
          </div>
        </main>
      )}

      <SidePanel
        totalPosts={totalPosts}
        onTopicClick={(topic) => {
          setActiveTab('explore');
          setSortBy('popular');
          showMessage(`正在查看話題：${topic}`);
        }}
        onClubClick={(club) => showMessage(`${club} 球會頁面將在下一版接入。`)}
        onEventClick={(event) => showMessage(`${event} 活動頁面將在下一版接入。`)}
      />
    </div>
  );
};

export default CommunityPage;
