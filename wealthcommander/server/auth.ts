import { promises as fs } from 'fs';
import bcrypt from 'bcrypt';
import { join } from 'path';
import { logger } from './logger';

interface User {
  id: string;
  username: string;
  email: string;
  passwordHash: string;
  role: string;
  createdAt: string;
  lastLogin: string | null;
  loginAttempts: number;
  lockedUntil: string | null;
  settings: {
    theme: string;
    language: string;
    notifications: boolean;
  };
  allowedAccounts: string[];
}

interface UserData {
  users: User[];
}

interface LoginAttempt {
  userId: string;
  timestamp: string;
  success: boolean;
  ip?: string;
}

class AuthService {
  private usersFilePath: string = join(process.cwd(), 'data', 'users.json');
  private maxLoginAttempts: number = 5;
  private lockoutDuration: number = 15 * 60 * 1000; // 15분

  async loadUsers(): Promise<UserData> {
    try {
      const data = await fs.readFile(this.usersFilePath, 'utf-8');
      return JSON.parse(data);
    } catch (error) {
      console.error('Failed to load users:', error);
      return { users: [] };
    }
  }

  async saveUsers(userData: UserData): Promise<void> {
    try {
      await fs.writeFile(this.usersFilePath, JSON.stringify(userData, null, 2), 'utf-8');
    } catch (error) {
      console.error('Failed to save users:', error);
      throw new Error('Failed to save user data');
    }
  }

  async authenticateUser(username: string, password: string, ip?: string): Promise<{ success: boolean; user?: Omit<User, 'passwordHash'>; message: string }> {
    const userData = await this.loadUsers();
    const user = userData.users.find(u => u.username === username);

    if (!user) {
      // 로그인 시도 기록 (실패)
      await logger.logLoginAttempt('unknown', false, ip);
      return { success: false, message: '사용자명 또는 비밀번호가 올바르지 않습니다.' };
    }

    // 계정 잠금 확인
    if (user.lockedUntil && new Date() < new Date(user.lockedUntil)) {
      const unlockTime = new Date(user.lockedUntil).toLocaleString('ko-KR');
      return { success: false, message: `계정이 잠겨있습니다. 잠금 해제 시간: ${unlockTime}` };
    }

    // 비밀번호 확인
    const isValidPassword = await bcrypt.compare(password, user.passwordHash);

    if (!isValidPassword) {
      // 로그인 실패 처리
      user.loginAttempts += 1;
      
      if (user.loginAttempts >= this.maxLoginAttempts) {
        user.lockedUntil = new Date(Date.now() + this.lockoutDuration).toISOString();
        user.loginAttempts = 0; // 잠금 후 시도 횟수 초기화
      }

      await this.saveUsers(userData);
      await logger.logLoginAttempt(user.username, false, ip);

      const remainingAttempts = this.maxLoginAttempts - user.loginAttempts;
      if (remainingAttempts > 0) {
        return { success: false, message: `사용자명 또는 비밀번호가 올바르지 않습니다. (남은 시도: ${remainingAttempts}회)` };
      } else {
        return { success: false, message: '로그인 시도 횟수를 초과했습니다. 계정이 15분간 잠겼습니다.' };
      }
    }

    // 로그인 성공
    user.loginAttempts = 0;
    user.lockedUntil = null;
    user.lastLogin = new Date().toISOString();
    await this.saveUsers(userData);
    await logger.logLoginAttempt(user.username, true, ip);

    // 비밀번호 해시를 제외한 사용자 정보 반환
    const { passwordHash, ...userInfo } = user;
    return { success: true, user: userInfo, message: '로그인 성공' };
  }

  async getUserById(id: string): Promise<Omit<User, 'passwordHash'> | null> {
    const userData = await this.loadUsers();
    const user = userData.users.find(u => u.id === id);
    
    if (!user) return null;
    
    const { passwordHash, ...userInfo } = user;
    return userInfo;
  }

  async changePassword(userId: string, currentPassword: string, newPassword: string): Promise<{ success: boolean; message: string }> {
    const userData = await this.loadUsers();
    const user = userData.users.find(u => u.id === userId);

    if (!user) {
      return { success: false, message: '사용자를 찾을 수 없습니다.' };
    }

    // 현재 비밀번호 확인
    const isValidCurrentPassword = await bcrypt.compare(currentPassword, user.passwordHash);
    if (!isValidCurrentPassword) {
      return { success: false, message: '현재 비밀번호가 올바르지 않습니다.' };
    }

    // 새 비밀번호 유효성 검사
    if (newPassword.length < 8) {
      return { success: false, message: '비밀번호는 최소 8자 이상이어야 합니다.' };
    }

    // 새 비밀번호 해싱
    const saltRounds = 10;
    const newPasswordHash = await bcrypt.hash(newPassword, saltRounds);
    user.passwordHash = newPasswordHash;

    await this.saveUsers(userData);
    return { success: true, message: '비밀번호가 변경되었습니다.' };
  }

  private async logLoginAttempt(attempt: LoginAttempt): Promise<void> {
    try {
      // 실제 환경에서는 별도의 로그 파일이나 데이터베이스에 저장
      console.log(`Login attempt: ${JSON.stringify(attempt)}`);
    } catch (error) {
      console.error('Failed to log login attempt:', error);
    }
  }

  async unlockAccount(userId: string): Promise<{ success: boolean; message: string }> {
    const userData = await this.loadUsers();
    const user = userData.users.find(u => u.id === userId);

    if (!user) {
      return { success: false, message: '사용자를 찾을 수 없습니다.' };
    }

    user.loginAttempts = 0;
    user.lockedUntil = null;
    await this.saveUsers(userData);

    return { success: true, message: '계정 잠금이 해제되었습니다.' };
  }

  async hasAccountAccess(userId: string, accountId: string): Promise<boolean> {
    const userData = await this.loadUsers();
    const user = userData.users.find(u => u.id === userId);

    if (!user) {
      return false;
    }

    // admin은 모든 계좌에 접근 가능
    if (user.role === 'admin' || user.allowedAccounts.includes('all')) {
      return true;
    }

    // 허용된 계좌 목록에 포함되어 있는지 확인
    return user.allowedAccounts.includes(accountId);
  }

  async getAllowedAccounts(userId: string): Promise<string[]> {
    const userData = await this.loadUsers();
    const user = userData.users.find(u => u.id === userId);

    if (!user) {
      return [];
    }

    // admin은 모든 계좌에 접근 가능
    if (user.role === 'admin' || user.allowedAccounts.includes('all')) {
      return ['all'];
    }

    return user.allowedAccounts;
  }
}

export const authService = new AuthService();