"""Seed initial questions for Part 2 — Daily/Weekly/Monthly Challenges.

Run this script after running the database migration:
    python scripts/seed_part2_questions.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.challenges import Question


# 30 Easy questions for daily challenges
EASY_QUESTIONS = [
    {
        "title": "Two Sum",
        "difficulty": "easy",
        "problem_statement": "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.",
        "constraints": "2 <= nums.length <= 10^4\n-10^9 <= nums[i] <= 10^9\n-10^9 <= target <= 10^9",
        "input_format": "First line: array of integers\nSecond line: target integer",
        "output_format": "Two space-separated integers representing the indices",
        "sample_input_1": "[2,7,11,15]\n9",
        "sample_output_1": "0 1",
        "sample_input_2": "[3,2,4]\n6",
        "sample_output_2": "1 2",
        "tags": ["array", "hash-table"],
        "time_limit_ms": 2000,
        "memory_limit_mb": 256,
    },
    {
        "title": "Reverse String",
        "difficulty": "easy",
        "problem_statement": "Write a function that reverses a string. The input string is given as an array of characters.",
        "constraints": "1 <= s.length <= 10^5\ns[i] is a printable ascii character",
        "input_format": "A string",
        "output_format": "The reversed string",
        "sample_input_1": "hello",
        "sample_output_1": "olleh",
        "sample_input_2": "HireX",
        "sample_output_2": "XeriH",
        "tags": ["string", "two-pointers"],
        "time_limit_ms": 2000,
        "memory_limit_mb": 256,
    },
    {
        "title": "Valid Palindrome",
        "difficulty": "easy",
        "problem_statement": "A phrase is a palindrome if, after converting all uppercase letters into lowercase letters and removing all non-alphanumeric characters, it reads the same forward and backward.",
        "constraints": "1 <= s.length <= 2 * 10^5\ns consists only of printable ASCII characters",
        "input_format": "A string",
        "output_format": "true or false",
        "sample_input_1": "A man, a plan, a canal: Panama",
        "sample_output_1": "true",
        "sample_input_2": "race a car",
        "sample_output_2": "false",
        "tags": ["string", "two-pointers"],
        "time_limit_ms": 2000,
        "memory_limit_mb": 256,
    },
    {
        "title": "Maximum Subarray",
        "difficulty": "easy",
        "problem_statement": "Given an integer array nums, find the contiguous subarray which has the largest sum and return its sum.",
        "constraints": "1 <= nums.length <= 10^5\n-10^4 <= nums[i] <= 10^4",
        "input_format": "Array of integers",
        "output_format": "Single integer - maximum sum",
        "sample_input_1": "[-2,1,-3,4,-1,2,1,-5,4]",
        "sample_output_1": "6",
        "sample_input_2": "[1]",
        "sample_output_2": "1",
        "tags": ["array", "dynamic-programming"],
        "time_limit_ms": 2000,
        "memory_limit_mb": 256,
    },
    {
        "title": "Merge Two Sorted Lists",
        "difficulty": "easy",
        "problem_statement": "Merge two sorted linked lists and return it as a sorted list.",
        "constraints": "The number of nodes in both lists is in the range [0, 50]\n-100 <= Node.val <= 100",
        "input_format": "Two space-separated sorted arrays",
        "output_format": "Merged sorted array",
        "sample_input_1": "[1,2,4] [1,3,4]",
        "sample_output_1": "[1,1,2,3,4,4]",
        "sample_input_2": "[] []",
        "sample_output_2": "[]",
        "tags": ["linked-list", "recursion"],
        "time_limit_ms": 2000,
        "memory_limit_mb": 256,
    },
    {
        "title": "Best Time to Buy and Sell Stock",
        "difficulty": "easy",
        "problem_statement": "You are given an array prices where prices[i] is the price of a given stock on the ith day. You want to maximize your profit by choosing a single day to buy one stock and choosing a different day in the future to sell that stock.",
        "constraints": "1 <= prices.length <= 10^5\n0 <= prices[i] <= 10^4",
        "input_format": "Array of integers",
        "output_format": "Maximum profit",
        "sample_input_1": "[7,1,5,3,6,4]",
        "sample_output_1": "5",
        "sample_input_2": "[7,6,4,3,1]",
        "sample_output_2": "0",
        "tags": ["array", "dynamic-programming"],
        "time_limit_ms": 2000,
        "memory_limit_mb": 256,
    },
    {
        "title": "Valid Parentheses",
        "difficulty": "easy",
        "problem_statement": "Given a string s containing just the characters '(', ')', '{', '}', '[' and ']', determine if the input string is valid.",
        "constraints": "1 <= s.length <= 10^4\ns consists of parentheses only '()[]{}'",
        "input_format": "A string",
        "output_format": "true or false",
        "sample_input_1": "()",
        "sample_output_1": "true",
        "sample_input_2": "([)]",
        "sample_output_2": "false",
        "tags": ["string", "stack"],
        "time_limit_ms": 2000,
        "memory_limit_mb": 256,
    },
    {
        "title": "Remove Duplicates from Sorted Array",
        "difficulty": "easy",
        "problem_statement": "Given an integer array nums sorted in non-decreasing order, remove the duplicates in-place such that each unique element appears only once.",
        "constraints": "1 <= nums.length <= 3 * 10^4\n-100 <= nums[i] <= 100",
        "input_format": "Sorted array of integers",
        "output_format": "Length of array after removing duplicates",
        "sample_input_1": "[1,1,2]",
        "sample_output_1": "2",
        "sample_input_2": "[0,0,1,1,1,2,2,3,3,4]",
        "sample_output_2": "5",
        "tags": ["array", "two-pointers"],
        "time_limit_ms": 2000,
        "memory_limit_mb": 256,
    },
    {
        "title": "Climbing Stairs",
        "difficulty": "easy",
        "problem_statement": "You are climbing a staircase. It takes n steps to reach the top. Each time you can either climb 1 or 2 steps. In how many distinct ways can you climb to the top?",
        "constraints": "1 <= n <= 45",
        "input_format": "Single integer n",
        "output_format": "Number of ways",
        "sample_input_1": "2",
        "sample_output_1": "2",
        "sample_input_2": "3",
        "sample_output_2": "3",
        "tags": ["dynamic-programming", "math"],
        "time_limit_ms": 2000,
        "memory_limit_mb": 256,
    },
    {
        "title": "Binary Search",
        "difficulty": "easy",
        "problem_statement": "Given an array of integers nums which is sorted in ascending order, and an integer target, write a function to search target in nums. If target exists, then return its index. Otherwise, return -1.",
        "constraints": "1 <= nums.length <= 10^4\n-10^4 < nums[i], target < 10^4",
        "input_format": "First line: sorted array\nSecond line: target",
        "output_format": "Index or -1",
        "sample_input_1": "[-1,0,3,5,9,12]\n9",
        "sample_output_1": "4",
        "sample_input_2": "[-1,0,3,5,9,12]\n2",
        "sample_output_2": "-1",
        "tags": ["array", "binary-search"],
        "time_limit_ms": 2000,
        "memory_limit_mb": 256,
    },
]

# Add 20 more easy questions
EASY_QUESTIONS.extend([
    {
        "title": f"Easy Problem {i}",
        "difficulty": "easy",
        "problem_statement": f"This is easy problem number {i}. Solve it efficiently.",
        "constraints": "Standard constraints apply",
        "input_format": "Input format",
        "output_format": "Output format",
        "sample_input_1": "sample input",
        "sample_output_1": "sample output",
        "sample_input_2": "sample input 2",
        "sample_output_2": "sample output 2",
        "tags": ["array", "string"],
        "time_limit_ms": 2000,
        "memory_limit_mb": 256,
    }
    for i in range(11, 31)
])

# 10 Medium questions for weekly challenges
MEDIUM_QUESTIONS = [
    {
        "title": "3Sum",
        "difficulty": "medium",
        "problem_statement": "Given an integer array nums, return all the triplets [nums[i], nums[j], nums[k]] such that i != j, i != k, and j != k, and nums[i] + nums[j] + nums[k] == 0.",
        "constraints": "3 <= nums.length <= 3000\n-10^5 <= nums[i] <= 10^5",
        "input_format": "Array of integers",
        "output_format": "List of triplets",
        "sample_input_1": "[-1,0,1,2,-1,-4]",
        "sample_output_1": "[[-1,-1,2],[-1,0,1]]",
        "sample_input_2": "[0,1,1]",
        "sample_output_2": "[]",
        "tags": ["array", "two-pointers", "sorting"],
        "time_limit_ms": 3000,
        "memory_limit_mb": 256,
    },
    {
        "title": "Longest Substring Without Repeating Characters",
        "difficulty": "medium",
        "problem_statement": "Given a string s, find the length of the longest substring without repeating characters.",
        "constraints": "0 <= s.length <= 5 * 10^4\ns consists of English letters, digits, symbols and spaces",
        "input_format": "A string",
        "output_format": "Length of longest substring",
        "sample_input_1": "abcabcbb",
        "sample_output_1": "3",
        "sample_input_2": "bbbbb",
        "sample_output_2": "1",
        "tags": ["string", "sliding-window", "hash-table"],
        "time_limit_ms": 3000,
        "memory_limit_mb": 256,
    },
    {
        "title": "Container With Most Water",
        "difficulty": "medium",
        "problem_statement": "You are given an integer array height of length n. There are n vertical lines drawn such that the two endpoints of the ith line are (i, 0) and (i, height[i]). Find two lines that together with the x-axis form a container, such that the container contains the most water.",
        "constraints": "n == height.length\n2 <= n <= 10^5\n0 <= height[i] <= 10^4",
        "input_format": "Array of integers",
        "output_format": "Maximum area",
        "sample_input_1": "[1,8,6,2,5,4,8,3,7]",
        "sample_output_1": "49",
        "sample_input_2": "[1,1]",
        "sample_output_2": "1",
        "tags": ["array", "two-pointers", "greedy"],
        "time_limit_ms": 3000,
        "memory_limit_mb": 256,
    },
    {
        "title": "Group Anagrams",
        "difficulty": "medium",
        "problem_statement": "Given an array of strings strs, group the anagrams together. You can return the answer in any order.",
        "constraints": "1 <= strs.length <= 10^4\n0 <= strs[i].length <= 100",
        "input_format": "Array of strings",
        "output_format": "Grouped anagrams",
        "sample_input_1": '["eat","tea","tan","ate","nat","bat"]',
        "sample_output_1": '[["bat"],["nat","tan"],["ate","eat","tea"]]',
        "sample_input_2": '[""]',
        "sample_output_2": '[[""]]',
        "tags": ["array", "hash-table", "string", "sorting"],
        "time_limit_ms": 3000,
        "memory_limit_mb": 256,
    },
    {
        "title": "Product of Array Except Self",
        "difficulty": "medium",
        "problem_statement": "Given an integer array nums, return an array answer such that answer[i] is equal to the product of all the elements of nums except nums[i].",
        "constraints": "2 <= nums.length <= 10^5\n-30 <= nums[i] <= 30",
        "input_format": "Array of integers",
        "output_format": "Array of products",
        "sample_input_1": "[1,2,3,4]",
        "sample_output_1": "[24,12,8,6]",
        "sample_input_2": "[-1,1,0,-3,3]",
        "sample_output_2": "[0,0,9,0,0]",
        "tags": ["array", "prefix-sum"],
        "time_limit_ms": 3000,
        "memory_limit_mb": 256,
    },
]

# Add 5 more medium questions
MEDIUM_QUESTIONS.extend([
    {
        "title": f"Medium Problem {i}",
        "difficulty": "medium",
        "problem_statement": f"This is medium problem number {i}. Requires intermediate algorithms.",
        "constraints": "Standard constraints apply",
        "input_format": "Input format",
        "output_format": "Output format",
        "sample_input_1": "sample input",
        "sample_output_1": "sample output",
        "sample_input_2": "sample input 2",
        "sample_output_2": "sample output 2",
        "tags": ["array", "dynamic-programming"],
        "time_limit_ms": 3000,
        "memory_limit_mb": 256,
    }
    for i in range(6, 11)
])

# 5 Hard questions for monthly challenges
HARD_QUESTIONS = [
    {
        "title": "Median of Two Sorted Arrays",
        "difficulty": "hard",
        "problem_statement": "Given two sorted arrays nums1 and nums2 of size m and n respectively, return the median of the two sorted arrays.",
        "constraints": "nums1.length == m\nnums2.length == n\n0 <= m <= 1000\n0 <= n <= 1000\n1 <= m + n <= 2000",
        "input_format": "Two sorted arrays",
        "output_format": "Median value",
        "sample_input_1": "[1,3] [2]",
        "sample_output_1": "2.0",
        "sample_input_2": "[1,2] [3,4]",
        "sample_output_2": "2.5",
        "tags": ["array", "binary-search", "divide-and-conquer"],
        "time_limit_ms": 5000,
        "memory_limit_mb": 256,
    },
    {
        "title": "Trapping Rain Water",
        "difficulty": "hard",
        "problem_statement": "Given n non-negative integers representing an elevation map where the width of each bar is 1, compute how much water it can trap after raining.",
        "constraints": "n == height.length\n1 <= n <= 2 * 10^4\n0 <= height[i] <= 10^5",
        "input_format": "Array of integers",
        "output_format": "Total water trapped",
        "sample_input_1": "[0,1,0,2,1,0,1,3,2,1,2,1]",
        "sample_output_1": "6",
        "sample_input_2": "[4,2,0,3,2,5]",
        "sample_output_2": "9",
        "tags": ["array", "two-pointers", "dynamic-programming", "stack"],
        "time_limit_ms": 5000,
        "memory_limit_mb": 256,
    },
    {
        "title": "Longest Valid Parentheses",
        "difficulty": "hard",
        "problem_statement": "Given a string containing just the characters '(' and ')', return the length of the longest valid (well-formed) parentheses substring.",
        "constraints": "0 <= s.length <= 3 * 10^4\ns[i] is '(', or ')'",
        "input_format": "A string",
        "output_format": "Length of longest valid substring",
        "sample_input_1": "(()",
        "sample_output_1": "2",
        "sample_input_2": ")()())",
        "sample_output_2": "4",
        "tags": ["string", "dynamic-programming", "stack"],
        "time_limit_ms": 5000,
        "memory_limit_mb": 256,
    },
    {
        "title": "Regular Expression Matching",
        "difficulty": "hard",
        "problem_statement": "Given an input string s and a pattern p, implement regular expression matching with support for '.' and '*' where '.' matches any single character and '*' matches zero or more of the preceding element.",
        "constraints": "1 <= s.length <= 20\n1 <= p.length <= 20\ns contains only lowercase English letters\np contains only lowercase English letters, '.', and '*'",
        "input_format": "Two strings: s and p",
        "output_format": "true or false",
        "sample_input_1": "aa a",
        "sample_output_1": "false",
        "sample_input_2": "aa a*",
        "sample_output_2": "true",
        "tags": ["string", "dynamic-programming", "recursion"],
        "time_limit_ms": 5000,
        "memory_limit_mb": 256,
    },
    {
        "title": "Merge k Sorted Lists",
        "difficulty": "hard",
        "problem_statement": "You are given an array of k linked-lists lists, each linked-list is sorted in ascending order. Merge all the linked-lists into one sorted linked-list and return it.",
        "constraints": "k == lists.length\n0 <= k <= 10^4\n0 <= lists[i].length <= 500",
        "input_format": "k sorted arrays",
        "output_format": "Merged sorted array",
        "sample_input_1": "[[1,4,5],[1,3,4],[2,6]]",
        "sample_output_1": "[1,1,2,3,4,4,5,6]",
        "sample_input_2": "[]",
        "sample_output_2": "[]",
        "tags": ["linked-list", "divide-and-conquer", "heap", "merge-sort"],
        "time_limit_ms": 5000,
        "memory_limit_mb": 256,
    },
]


async def seed_questions():
    """Seed all questions into the database."""
    async with AsyncSessionLocal() as db:
        try:
            # Check if questions already exist
            result = await db.execute(select(Question).limit(1))
            existing = result.scalar_one_or_none()
            
            if existing:
                print("⚠️  Questions already exist in database. Skipping seed.")
                print("   To re-seed, delete existing questions first.")
                return
            
            print("🌱 Seeding questions...")
            
            # Seed easy questions
            print(f"   Adding {len(EASY_QUESTIONS)} easy questions...")
            for q_data in EASY_QUESTIONS:
                question = Question(**q_data)
                db.add(question)
            
            # Seed medium questions
            print(f"   Adding {len(MEDIUM_QUESTIONS)} medium questions...")
            for q_data in MEDIUM_QUESTIONS:
                question = Question(**q_data)
                db.add(question)
            
            # Seed hard questions
            print(f"   Adding {len(HARD_QUESTIONS)} hard questions...")
            for q_data in HARD_QUESTIONS:
                question = Question(**q_data)
                db.add(question)
            
            await db.commit()
            
            print(f"✅ Successfully seeded {len(EASY_QUESTIONS) + len(MEDIUM_QUESTIONS) + len(HARD_QUESTIONS)} questions!")
            print(f"   - Easy: {len(EASY_QUESTIONS)}")
            print(f"   - Medium: {len(MEDIUM_QUESTIONS)}")
            print(f"   - Hard: {len(HARD_QUESTIONS)}")
            
        except Exception as e:
            print(f"❌ Error seeding questions: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    print("=" * 60)
    print("HireX Part 2 — Question Seeding Script")
    print("=" * 60)
    asyncio.run(seed_questions())
    print("=" * 60)
