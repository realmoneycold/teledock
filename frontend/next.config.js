/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'bypass-tunnel-reminder',
            value: 'true',
          },
        ],
      },
    ];
  },
}

module.exports = nextConfig
