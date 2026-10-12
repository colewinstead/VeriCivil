CREATE TABLE `engineering_samples` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`event_day` text NOT NULL,
	`standard` text NOT NULL,
	`speed` real NOT NULL,
	`radius` real NOT NULL,
	`pc` text NOT NULL,
	`pt` text NOT NULL,
	`sample_count` integer DEFAULT 1 NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `engineering_samples_daily_idx` ON `engineering_samples` (`event_day`,`standard`,`speed`,`radius`,`pc`,`pt`);--> statement-breakpoint
CREATE TABLE `retained_landxml` (
	`id` text PRIMARY KEY NOT NULL,
	`content` text NOT NULL,
	`bytes` integer NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
