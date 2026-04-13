"""Seed coding questions with test cases.

Revision ID: 010
Revises: 009
"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None

EASY = [
    ("Two Sum", "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.\n\nYou may assume each input has exactly one solution, and you may not use the same element twice.", "2 <= nums.length <= 10^4\n-10^9 <= nums[i] <= 10^9", "First line: space-separated integers\nSecond line: target integer", "Two space-separated indices", "2 7 11 15\n9", "0 1", "3 2 4\n6", "1 2", [{"input":"2 7 11 15\n9","expected_output":"0 1"},{"input":"3 2 4\n6","expected_output":"1 2"},{"input":"3 3\n6","expected_output":"0 1"}], ["array","hash-table"]),
    ("Reverse String", "Write a function that reverses a string. The input string is given as an array of characters s.\n\nYou must do this by modifying the input array in-place with O(1) extra memory.", "1 <= s.length <= 10^5\ns[i] is a printable ASCII character.", "A single string", "The reversed string", "hello", "olleh", "Hannah", "hannaH", [{"input":"hello","expected_output":"olleh"},{"input":"Hannah","expected_output":"hannaH"},{"input":"a","expected_output":"a"}], ["string","two-pointers"]),
    ("Valid Parentheses", "Given a string s containing just the characters (, ), {, }, [ and ], determine if the input string is valid.\n\nAn input string is valid if open brackets are closed by the same type, in the correct order, and every close bracket has a corresponding open bracket.", "1 <= s.length <= 10^4\ns consists of parentheses only ()[]{}.", "A string of bracket characters", "true or false", "()", "true", "()[]{}", "true", [{"input":"()","expected_output":"true"},{"input":"()[]{}","expected_output":"true"},{"input":"(]","expected_output":"false"},{"input":"([)]","expected_output":"false"},{"input":"{[]}","expected_output":"true"}], ["stack","string"]),
    ("FizzBuzz", "Given an integer n, return a string array where answer[i] is FizzBuzz if i divisible by 3 and 5, Fizz if divisible by 3, Buzz if divisible by 5, else the number as string. i is 1-indexed.", "1 <= n <= 10^4", "A single integer n", "Space-separated strings for i from 1 to n", "3", "1 2 Fizz", "5", "1 2 Fizz 4 Buzz", [{"input":"3","expected_output":"1 2 Fizz"},{"input":"5","expected_output":"1 2 Fizz 4 Buzz"},{"input":"15","expected_output":"1 2 Fizz 4 Buzz Fizz 7 8 Fizz Buzz 11 Fizz 13 14 FizzBuzz"}], ["math","string","simulation"]),
    ("Palindrome Number", "Given an integer x, return true if x is a palindrome, and false otherwise. An integer is a palindrome when it reads the same forward and backward.", "-2^31 <= x <= 2^31 - 1", "A single integer", "true or false", "121", "true", "-121", "false", [{"input":"121","expected_output":"true"},{"input":"-121","expected_output":"false"},{"input":"10","expected_output":"false"},{"input":"1221","expected_output":"true"}], ["math"]),
    ("Best Time to Buy and Sell Stock", "You are given an array prices where prices[i] is the price of a stock on day i. Maximize profit by choosing one day to buy and a later day to sell. Return the maximum profit, or 0 if no profit is possible.", "1 <= prices.length <= 10^5\n0 <= prices[i] <= 10^4", "Space-separated integers (prices)", "A single integer (max profit)", "7 1 5 3 6 4", "5", "7 6 4 3 1", "0", [{"input":"7 1 5 3 6 4","expected_output":"5"},{"input":"7 6 4 3 1","expected_output":"0"},{"input":"1 2","expected_output":"1"},{"input":"2 4 1 7","expected_output":"6"}], ["array","dynamic-programming"]),
    ("Missing Number", "Given an array nums containing n distinct numbers in the range [0, n], return the only number in the range that is missing from the array.", "n == nums.length\n1 <= n <= 10^4\n0 <= nums[i] <= n\nAll numbers are unique.", "Space-separated integers", "A single integer", "3 0 1", "2", "0 1", "2", [{"input":"3 0 1","expected_output":"2"},{"input":"0 1","expected_output":"2"},{"input":"9 6 4 2 3 5 7 0 1","expected_output":"8"}], ["array","math","bit-manipulation"]),
    ("Single Number", "Given a non-empty array of integers nums, every element appears twice except for one. Find that single one. Implement with O(n) time and O(1) space.", "1 <= nums.length <= 3 * 10^4\n-3 * 10^4 <= nums[i] <= 3 * 10^4\nEach element appears twice except for one.", "Space-separated integers", "A single integer", "2 2 1", "1", "4 1 2 1 2", "4", [{"input":"2 2 1","expected_output":"1"},{"input":"4 1 2 1 2","expected_output":"4"},{"input":"1","expected_output":"1"}], ["array","bit-manipulation"]),
]

MEDIUM = [
    ("Longest Substring Without Repeating Characters", "Given a string s, find the length of the longest substring without repeating characters.", "0 <= s.length <= 5 * 10^4\ns consists of English letters, digits, symbols and spaces.", "A single string", "A single integer", "abcabcbb", "3", "bbbbb", "1", [{"input":"abcabcbb","expected_output":"3"},{"input":"bbbbb","expected_output":"1"},{"input":"pwwkew","expected_output":"3"},{"input":"","expected_output":"0"}], ["hash-table","string","sliding-window"]),
    ("Container With Most Water", "You are given an integer array height of length n. Find two lines that together with the x-axis form a container that holds the most water. Return the maximum amount of water.", "n == height.length\n2 <= n <= 10^5\n0 <= height[i] <= 10^4", "Space-separated integers (heights)", "A single integer (max water)", "1 8 6 2 5 4 8 3 7", "49", "1 1", "1", [{"input":"1 8 6 2 5 4 8 3 7","expected_output":"49"},{"input":"1 1","expected_output":"1"},{"input":"4 3 2 1 4","expected_output":"16"}], ["array","two-pointers","greedy"]),
    ("Jump Game", "You are given an integer array nums. You are initially positioned at index 0, and each element represents your maximum jump length. Return true if you can reach the last index, or false otherwise.", "1 <= nums.length <= 10^4\n0 <= nums[i] <= 10^5", "Space-separated integers", "true or false", "2 3 1 1 4", "true", "3 2 1 0 4", "false", [{"input":"2 3 1 1 4","expected_output":"true"},{"input":"3 2 1 0 4","expected_output":"false"},{"input":"0","expected_output":"true"},{"input":"1 0 0","expected_output":"false"}], ["array","dynamic-programming","greedy"]),
    ("Coin Change", "You are given an integer array coins representing coins of different denominations and an integer amount. Return the fewest number of coins needed to make up that amount. If that amount cannot be made up, return -1.", "1 <= coins.length <= 12\n1 <= coins[i] <= 2^31 - 1\n0 <= amount <= 10^4", "First line: space-separated coin denominations\nSecond line: target amount", "A single integer", "1 5 10 25\n36", "3", "2\n3", "-1", [{"input":"1 5 10 25\n36","expected_output":"3"},{"input":"2\n3","expected_output":"-1"},{"input":"1\n0","expected_output":"0"},{"input":"1 2 5\n11","expected_output":"3"}], ["array","dynamic-programming","bfs"]),
    ("Product of Array Except Self", "Given an integer array nums, return an array answer such that answer[i] is equal to the product of all the elements of nums except nums[i]. Solve in O(n) without using division.", "2 <= nums.length <= 10^5\n-30 <= nums[i] <= 30\nThe product of any prefix or suffix of nums is guaranteed to fit in a 32-bit integer.", "Space-separated integers", "Space-separated integers", "1 2 3 4", "24 12 8 6", "2 3 4 5", "60 40 30 24", [{"input":"1 2 3 4","expected_output":"24 12 8 6"},{"input":"2 3 4 5","expected_output":"60 40 30 24"},{"input":"-1 1 0 -3 3","expected_output":"0 0 9 0 0"}], ["array","prefix-sum"]),
    ("Find Peak Element", "A peak element is an element that is strictly greater than its neighbors. Given a 0-indexed integer array nums, find a peak element, and return its index. If multiple peaks exist, return any. Solve in O(log n).", "1 <= nums.length <= 1000\n-2^31 <= nums[i] <= 2^31 - 1\nnums[i] != nums[i+1] for all valid i.", "Space-separated integers", "A single integer (index)", "1 2 3 1", "2", "1 2 1 3 5 6 4", "5", [{"input":"1 2 3 1","expected_output":"2"},{"input":"1","expected_output":"0"},{"input":"1 2","expected_output":"1"}], ["array","binary-search"]),
    ("Rotate Array", "Given an integer array nums, rotate the array to the right by k steps, where k is non-negative.", "1 <= nums.length <= 10^5\n-2^31 <= nums[i] <= 2^31 - 1\n0 <= k <= 10^5", "First line: space-separated integers\nSecond line: k", "Space-separated integers (rotated)", "1 2 3 4 5 6 7\n3", "5 6 7 1 2 3 4", "1 2\n3", "2 1", [{"input":"1 2 3 4 5 6 7\n3","expected_output":"5 6 7 1 2 3 4"},{"input":"1 2\n3","expected_output":"2 1"},{"input":"1 2 3\n0","expected_output":"1 2 3"}], ["array","math","two-pointers"]),
    ("Subarray Sum Equals K", "Given an array of integers nums and an integer k, return the total number of subarrays whose sum equals to k.", "1 <= nums.length <= 2 * 10^4\n-1000 <= nums[i] <= 1000\n-10^7 <= k <= 10^7", "First line: space-separated integers\nSecond line: k", "A single integer", "1 1 1\n2", "2", "1 2 3\n3", "2", [{"input":"1 1 1\n2","expected_output":"2"},{"input":"1 2 3\n3","expected_output":"2"},{"input":"1\n0","expected_output":"0"}], ["array","hash-table","prefix-sum"]),
]

HARD = [
    ("Trapping Rain Water", "Given n non-negative integers representing an elevation map where the width of each bar is 1, compute how much water it can trap after raining.", "n == height.length\n1 <= n <= 2 * 10^4\n0 <= height[i] <= 10^5", "Space-separated integers (heights)", "A single integer (total water trapped)", "0 1 0 2 1 0 1 3 2 1 2 1", "6", "4 2 0 3 2 5", "9", [{"input":"0 1 0 2 1 0 1 3 2 1 2 1","expected_output":"6"},{"input":"4 2 0 3 2 5","expected_output":"9"},{"input":"1 0 1","expected_output":"1"}], ["array","two-pointers","dynamic-programming","stack"]),
    ("Median of Two Sorted Arrays", "Given two sorted arrays nums1 and nums2 of size m and n respectively, return the median of the two sorted arrays. The overall run time complexity should be O(log(m+n)).", "0 <= m <= 1000\n0 <= n <= 1000\n1 <= m + n <= 2000\n-10^6 <= nums1[i], nums2[i] <= 10^6", "First line: space-separated integers (nums1, or empty)\nSecond line: space-separated integers (nums2)", "The median as a float (one decimal place)", "1 3\n2", "2.0", "1 2\n3 4", "2.5", [{"input":"1 3\n2","expected_output":"2.0"},{"input":"1 2\n3 4","expected_output":"2.5"},{"input":"0 0\n0 0","expected_output":"0.0"}], ["array","binary-search","divide-and-conquer"]),
    ("Longest Valid Parentheses", "Given a string containing just the characters ( and ), return the length of the longest valid (well-formed) parentheses substring.", "0 <= s.length <= 3 * 10^4\ns[i] is ( or ).", "A string of parentheses", "A single integer", "(()", "2", ")()())", "4", [{"input":"(()","expected_output":"2"},{"input":")()())","expected_output":"4"},{"input":"","expected_output":"0"},{"input":"()(()","expected_output":"2"}], ["string","dynamic-programming","stack"]),
    ("Minimum Window Substring", "Given two strings s and t of lengths m and n respectively, return the minimum window substring of s such that every character in t (including duplicates) is included in the window. If there is no such substring, return the empty string.", "m == s.length\nn == t.length\n1 <= m, n <= 10^5\ns and t consist of uppercase and lowercase English letters.", "First line: string s\nSecond line: string t", "The minimum window substring, or empty string", "ADOBECODEBANC\nABC", "BANC", "a\na", "a", [{"input":"ADOBECODEBANC\nABC","expected_output":"BANC"},{"input":"a\na","expected_output":"a"},{"input":"a\naa","expected_output":""}], ["hash-table","string","sliding-window"]),
]

def upgrade() -> None:
    conn = op.get_bind()

    # Use a table construct so SQLAlchemy handles type coercion
    questions_table = sa.table(
        "questions",
        sa.column("title", sa.String),
        sa.column("difficulty", sa.String),
        sa.column("problem_statement", sa.Text),
        sa.column("constraints", sa.Text),
        sa.column("input_format", sa.Text),
        sa.column("output_format", sa.Text),
        sa.column("sample_input_1", sa.Text),
        sa.column("sample_output_1", sa.Text),
        sa.column("sample_input_2", sa.Text),
        sa.column("sample_output_2", sa.Text),
        sa.column("test_cases", sa.JSON),
        sa.column("tags", sa.ARRAY(sa.String)),
        sa.column("is_active", sa.Boolean),
    )

    all_questions = (
        [(q, "easy") for q in EASY] +
        [(q, "medium") for q in MEDIUM] +
        [(q, "hard") for q in HARD]
    )
    for q, diff in all_questions:
        (title, problem_statement, constraints, input_format, output_format,
         sample_input_1, sample_output_1, sample_input_2, sample_output_2,
         test_cases, tags) = q
        # Check if already exists to avoid conflict
        exists = conn.execute(
            sa.text("SELECT 1 FROM questions WHERE title = :title"),
            {"title": title}
        ).fetchone()
        if exists:
            continue
        conn.execute(
            questions_table.insert().values(
                title=title,
                difficulty=diff,
                problem_statement=problem_statement,
                constraints=constraints,
                input_format=input_format,
                output_format=output_format,
                sample_input_1=sample_input_1,
                sample_output_1=sample_output_1,
                sample_input_2=sample_input_2,
                sample_output_2=sample_output_2,
                test_cases=test_cases,
                tags=tags,
                is_active=True,
            )
        )

def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM questions WHERE title IN ('Two Sum','Reverse String','Valid Parentheses','FizzBuzz','Palindrome Number','Best Time to Buy and Sell Stock','Missing Number','Single Number','Longest Substring Without Repeating Characters','Container With Most Water','Jump Game','Coin Change','Product of Array Except Self','Find Peak Element','Rotate Array','Subarray Sum Equals K','Trapping Rain Water','Median of Two Sorted Arrays','Longest Valid Parentheses','Minimum Window Substring')"))
