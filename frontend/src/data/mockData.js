// ── Mock Data ──────────────────────────────────────────────────────────────
export const MOCK_JOBS = [
  { id: 1, title: "Senior Frontend Engineer", department: "Engineering", experience: "4-6 years", location: "Remote", skills: ["React", "TypeScript", "GraphQL", "CSS"], status: "Active", created: "2024-06-10", applicants: 48 },
  { id: 2, title: "Product Designer", department: "Design", experience: "3-5 years", location: "Mumbai", skills: ["Figma", "UX Research", "Prototyping", "Design Systems"], status: "Active", created: "2024-06-08", applicants: 32 },
  { id: 3, title: "ML Engineer", department: "AI/ML", experience: "5+ years", location: "Bangalore", skills: ["PyTorch", "Python", "LLMs", "MLOps"], status: "Active", created: "2024-06-05", applicants: 27 },
  { id: 4, title: "DevOps Engineer", department: "Infrastructure", experience: "3-4 years", location: "Hybrid", skills: ["Kubernetes", "AWS", "Terraform", "CI/CD"], status: "Draft", created: "2024-06-01", applicants: 0 },
  { id: 5, title: "Backend Engineer (Go)", department: "Engineering", experience: "4+ years", location: "Remote", skills: ["Go", "gRPC", "PostgreSQL", "Redis"], status: "Closed", created: "2024-05-20", applicants: 61 },
  { id: 6, title: "Data Analyst", department: "Analytics", experience: "2-4 years", location: "Pune", skills: ["SQL", "Python", "Tableau", "Statistics"], status: "Active", created: "2024-06-12", applicants: 19 },
];

export const MOCK_CANDIDATES = [
  { id: 1, name: "Aisha Patel", email: "aisha.patel@email.com", phone: "+91 98765 43210", experience: "5 years", appliedJob: "Senior Frontend Engineer", jobId: 1, matchScore: 94, status: "Shortlisted", recommendation: "Highly Recommended", avatar: "AP", avatarColor: "#7C3AED", skills: ["React", "TypeScript", "CSS", "GraphQL", "Next.js"], missingSkills: [], education: "B.Tech CS, IIT Bombay", summary: "Exceptional candidate with deep React expertise and prior SaaS startup experience. Has led a team of 4 and shipped 3 production apps. Architecture thinking is strong.", experienceMatch: "Strong", educationMatch: "Strong" },
  { id: 2, name: "Rohan Mehta", email: "rohan.mehta@email.com", phone: "+91 87654 32109", experience: "4 years", appliedJob: "Senior Frontend Engineer", jobId: 1, matchScore: 81, status: "Pending", recommendation: "Recommended", avatar: "RM", avatarColor: "#0891B2", skills: ["React", "JavaScript", "CSS", "REST APIs"], missingSkills: ["TypeScript", "GraphQL"], education: "B.E. CS, Pune University", summary: "Good frontend foundation with React. Missing TypeScript and GraphQL but shows strong learning aptitude. Projects are well-structured.", experienceMatch: "Good", educationMatch: "Good" },
  { id: 3, name: "Priya Sharma", email: "priya.sharma@email.com", phone: "+91 76543 21098", experience: "6 years", appliedJob: "ML Engineer", jobId: 3, matchScore: 89, status: "Shortlisted", recommendation: "Highly Recommended", avatar: "PS", avatarColor: "#059669", skills: ["PyTorch", "Python", "NLP", "LLMs", "MLOps"], missingSkills: [], education: "M.Tech AI, IIT Delhi", summary: "Outstanding ML profile. Published 2 papers on LLMs, has production MLOps experience at a major tech company. Perfect fit.", experienceMatch: "Strong", educationMatch: "Strong" },
  { id: 4, name: "Amit Kumar", email: "amit.kumar@email.com", phone: "+91 65432 10987", experience: "3 years", appliedJob: "Product Designer", jobId: 2, matchScore: 72, status: "Pending", recommendation: "Consider", avatar: "AK", avatarColor: "#D97706", skills: ["Figma", "UX Research"], missingSkills: ["Prototyping", "Design Systems"], education: "BDes, NID Ahmedabad", summary: "Creative designer with solid Figma skills. Lacks exposure to mature design systems and advanced prototyping. Would benefit from mentorship.", experienceMatch: "Moderate", educationMatch: "Strong" },
  { id: 5, name: "Nisha Gupta", email: "nisha.gupta@email.com", phone: "+91 54321 09876", experience: "7 years", appliedJob: "DevOps Engineer", jobId: 4, matchScore: 91, status: "Pending", recommendation: "Highly Recommended", avatar: "NG", avatarColor: "#DB2777", skills: ["Kubernetes", "AWS", "Terraform", "CI/CD", "Docker"], missingSkills: [], education: "B.Tech IT, VIT Vellore", summary: "Expert DevOps engineer with hands-on Kubernetes and Terraform in production. Led cloud migration for 200+ microservices.", experienceMatch: "Strong", educationMatch: "Good" },
  { id: 6, name: "Vikram Singh", email: "vikram.singh@email.com", phone: "+91 43210 98765", experience: "2 years", appliedJob: "Data Analyst", jobId: 6, matchScore: 63, status: "Rejected", recommendation: "Not Recommended", avatar: "VS", avatarColor: "#DC2626", skills: ["SQL", "Excel"], missingSkills: ["Python", "Tableau", "Statistics"], education: "B.Com, DU", summary: "Limited technical skills for this role. Strong SQL knowledge but missing Python and visualization tools. Recommend for junior positions.", experienceMatch: "Weak", educationMatch: "Moderate" },
  { id: 7, name: "Kavya Reddy", email: "kavya.reddy@email.com", phone: "+91 32109 87654", experience: "5 years", appliedJob: "Backend Engineer (Go)", jobId: 5, matchScore: 88, status: "Shortlisted", recommendation: "Recommended", avatar: "KR", avatarColor: "#4F46E5", skills: ["Go", "gRPC", "PostgreSQL", "Redis", "Kafka"], missingSkills: [], education: "M.Sc CS, BITS Pilani", summary: "Solid Go engineer with microservices background. Experience with high-throughput systems is excellent. Strong database design skills.", experienceMatch: "Strong", educationMatch: "Strong" },
  { id: 8, name: "Dev Joshi", email: "dev.joshi@email.com", phone: "+91 21098 76543", experience: "3 years", appliedJob: "Product Designer", jobId: 2, matchScore: 76, status: "Pending", recommendation: "Consider", avatar: "DJ", avatarColor: "#0EA5E9", skills: ["Figma", "Prototyping", "User Research"], missingSkills: ["Design Systems"], education: "B.Des, Srishti Bangalore", summary: "Good all-rounder designer. Strong prototyping skills, decent user research process. Should build more on design system fundamentals.", experienceMatch: "Good", educationMatch: "Strong" },
];

export const MOCK_STATS = {
  totalCandidates: 187,
  activeJobs: 4,
  aiScreened: 142,
  pendingReviews: 23,
  shortlisted: 31,
  rejected: 18,
};

export const MOCK_ACTIVITY = [
  { id: 1, type: "upload", text: "8 resumes uploaded for Senior Frontend Engineer", time: "2 minutes ago", icon: "upload" },
  { id: 2, type: "screen", text: "AI screening completed for Product Designer role", time: "18 minutes ago", icon: "bot" },
  { id: 3, type: "shortlist", text: "Aisha Patel shortlisted for Senior Frontend Engineer", time: "1 hour ago", icon: "check" },
  { id: 4, type: "job", text: "New job posted: Data Analyst", time: "3 hours ago", icon: "briefcase" },
  { id: 5, type: "reject", text: "Vikram Singh rejected for Data Analyst", time: "5 hours ago", icon: "x" },
];

export const MOCK_APPLICATIONS_PER_JOB = [
  { name: "Frontend Eng.", applicants: 48 },
  { name: "Product Designer", applicants: 32 },
  { name: "ML Engineer", applicants: 27 },
  { name: "Backend (Go)", applicants: 61 },
  { name: "Data Analyst", applicants: 19 },
];

export const MOCK_STATUS_PIE = [
  { name: "Shortlisted", value: 31, color: "#22C55E" },
  { name: "Pending", value: 138, color: "#F59E0B" },
  { name: "Rejected", value: 18, color: "#EF4444" },
];

export const MOCK_FUNNEL = [
  { stage: "Applied", count: 187 },
  { stage: "AI Screened", count: 142 },
  { stage: "HR Review", count: 89 },
  { stage: "Shortlisted", count: 31 },
  { stage: "Interview", count: 14 },
  { stage: "Offered", count: 5 },
];

export const MOCK_MATCH_TREND = [
  { month: "Jan", avgScore: 68 },
  { month: "Feb", avgScore: 71 },
  { month: "Mar", avgScore: 74 },
  { month: "Apr", avgScore: 70 },
  { month: "May", avgScore: 78 },
  { month: "Jun", avgScore: 82 },
];

export const MOCK_TOP_SKILLS = [
  { skill: "React", count: 72 },
  { skill: "Python", count: 65 },
  { skill: "AWS", count: 48 },
  { skill: "TypeScript", count: 43 },
  { skill: "SQL", count: 58 },
  { skill: "Docker", count: 37 },
  { skill: "Node.js", count: 34 },
  { skill: "Figma", count: 28 },
];

export const DEPARTMENTS = [
  "Engineering",
  "Product",
  "Design",
  "UX Research",
  "AI/ML",
  "Data Science",
  "Analytics",
  "Infrastructure",
  "DevOps",
  "Cloud & Platform",
  "Cybersecurity",
  "Quality Assurance",
  "IT Support",
  "Human Resources",
  "Talent Acquisition",
  "Finance",
  "Legal & Compliance",
  "Sales",
  "Business Development",
  "Marketing",
  "Customer Success",
  "Operations",
  "Procurement",
  "Administration",
  "Research & Development",
  "Content",
  "Facilities",
];
